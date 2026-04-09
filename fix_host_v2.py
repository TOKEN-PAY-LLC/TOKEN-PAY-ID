#!/usr/bin/env python3
"""Fix host-level node process: find process manager, update, restart"""
import paramiko, time, os

SERVER = "5.23.54.205"
USER = "root"
PASSWORD = "vE^6t-zFS3dpNT"
BACKEND = r"c:\Users\user\Desktop\TokenPay-Website\backend"

def new_client():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(SERVER, port=22, username=USER, password=PASSWORD,
              timeout=120, banner_timeout=60, auth_timeout=60,
              allow_agent=False, look_for_keys=False)
    t = c.get_transport()
    t.set_keepalive(30)
    t.window_size = 4 * 1024 * 1024
    t.packetizer.REKEY_BYTES = pow(2, 40)
    t.packetizer.REKEY_PACKETS = pow(2, 40)
    return c

def run(c, cmd):
    _, stdout, stderr = c.exec_command(cmd, timeout=120)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if out:
        for line in out.split('\n')[:30]: print("  " + line)
    if err and 'warning' not in err.lower():
        for line in err.split('\n')[:5]: print("  ERR:", line)
    return out

c = new_client()

# 1. Find how the host process is managed
print("=== 1. Check process manager ===")
run(c, 'which pm2 2>/dev/null && pm2 list || echo "no pm2"')
print()
run(c, 'systemctl list-units --type=service --state=running | grep -iE "node|tokenpay|backend" || echo "no matching systemd services"')
print()
run(c, 'cat /etc/systemd/system/tokenpay*.service 2>/dev/null || echo "no tokenpay systemd service"')
print()
run(c, 'ls /etc/systemd/system/*node* /etc/systemd/system/*backend* /etc/systemd/system/*tokenpay* 2>/dev/null || echo "no systemd unit files found"')
print()
run(c, 'crontab -l 2>/dev/null | grep -i "node\|server\|tokenpay" || echo "no cron entries"')
print()
# Check if there's a supervisor or other process manager
run(c, 'ls /var/www/backend/ | head -20')
print()
run(c, 'cat /var/www/backend/ecosystem.config.js 2>/dev/null || echo "no pm2 ecosystem config"')
c.close()

# 2. Kill ALL host-level node processes and update files
print("\n=== 2. Kill all /var/www node processes ===")
c = new_client()
run(c, 'pkill -f "node /var/www/backend/server.js" 2>/dev/null; sleep 2; ps aux | grep "node /var/www" | grep -v grep || echo "All killed"')
c.close()

# 3. Upload new files
print("\n=== 3. Upload new code ===")
c = new_client()
sftp = c.open_sftp()
sftp.put(os.path.join(BACKEND, 'server.js'), '/var/www/backend/server.js')
sftp.put(os.path.join(BACKEND, 'email-service.js'), '/var/www/backend/email-service.js')
print("  Files uploaded")
sftp.close()

# 4. Verify files on disk
print("\n=== 4. Verify new code on disk ===")
run(c, 'grep -c "enterprise/errors" /var/www/backend/server.js && echo "enterprise routes: OK"')
run(c, 'grep -c "getGeoByIP" /var/www/backend/server.js && echo "geo: OK"')
run(c, 'head -1 /var/www/backend/email-service.js')
c.close()

# 5. Restart the host process (using whatever manager is available)
print("\n=== 5. Restart host process ===")
c = new_client()
# Try pm2 first, then systemd, then manual
out = run(c, 'which pm2 2>/dev/null')
if out and 'pm2' in out:
    print("  Using pm2...")
    run(c, 'pm2 restart all 2>&1 || pm2 start /var/www/backend/server.js --name tokenpay-host 2>&1')
else:
    # Manual restart with nohup
    print("  Manual restart...")
    run(c, 'cd /var/www/backend && NODE_ENV=production nohup node server.js >> /var/log/tokenpay-host.log 2>&1 & echo "PID: $!"')
time.sleep(5)
run(c, 'ps aux | grep "node.*server" | grep -v grep')
c.close()

# 6. Final verification
print("\n=== 6. Final verification ===")
c = new_client()
print("\n  Health (localhost:8080):")
run(c, 'curl -s http://localhost:8080/health')
print("\n  Preferences (localhost:8080):")
run(c, 'curl -s http://localhost:8080/api/v1/client/preferences')
print("\n  Enterprise errors POST:")
run(c, 'curl -s -X POST http://localhost:8080/api/v1/enterprise/errors -H "Content-Type: application/json" -d \'{"error_type":"test","error_message":"test"}\' -w "\\nHTTP:%{http_code}" | tail -3')
print("\n  ZH language:")
run(c, 'curl -s -H "Accept-Language: zh" http://localhost:8080/api/v1/client/preferences')
print("\n  Docker container still healthy:")
run(c, 'docker exec tokenpay-id-api wget -qO- http://localhost:8080/health 2>/dev/null')
c.close()
print("\nDone.")

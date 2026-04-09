#!/usr/bin/env python3
"""Kill old host-level node process and update /var/www/backend with new code"""
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

# Step 1: Kill old process
print("=== 1. Kill old host-level node process ===")
c = new_client()
run(c, 'kill 999744 2>/dev/null; sleep 1; ps aux | grep "node /var/www" | grep -v grep || echo "Process killed OK"')
c.close()

# Step 2: Upload new files
print("\n=== 2. Update /var/www/backend files ===")
c = new_client()
sftp = c.open_sftp()
sftp.put(os.path.join(BACKEND, 'server.js'), '/var/www/backend/server.js')
print("  Updated server.js")
sftp.put(os.path.join(BACKEND, 'email-service.js'), '/var/www/backend/email-service.js')
print("  Updated email-service.js")
sftp.close()
c.close()

# Step 3: Restart
print("\n=== 3. Restart host node process ===")
c = new_client()
run(c, 'cd /var/www/backend && nohup node server.js > /var/log/tokenpay-host.log 2>&1 & sleep 3 && echo "Started"')
run(c, 'ps aux | grep "node.*server" | grep -v grep')
c.close()

# Step 4: Verify
print("\n=== 4. Verify ===")
time.sleep(3)
c = new_client()
run(c, 'curl -s http://localhost:8080/health')
run(c, 'curl -s http://localhost:8080/api/v1/client/preferences')
run(c, 'curl -s -X POST http://localhost:8080/api/v1/enterprise/errors -H "Content-Type: application/json" -d \'{"error_type":"test"}\' -w "\\nHTTP:%{http_code}" 2>/dev/null | tail -3')
c.close()
print("\nDone.")

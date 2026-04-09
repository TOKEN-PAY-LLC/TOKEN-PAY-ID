#!/usr/bin/env python3
"""Deploy feature updates v2: fix extraction paths"""
import paramiko, tarfile, os, io, time

SERVER = "5.23.54.205"
USER = "root"
PASSWORD = "vE^6t-zFS3dpNT"

BACKEND = r"c:\Users\user\Desktop\TokenPay-Website\backend"
FRONTEND = r"c:\Users\user\Desktop\TokenPay-Website\frontend"

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

def run(c, cmd, show=True):
    _, stdout, stderr = c.exec_command(cmd, timeout=120)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if show and out:
        for line in out.split('\n')[:30]: print("  " + line)
    if show and err and 'warning' not in err.lower():
        for line in err.split('\n')[:5]: print("  ERR:", line)
    return out

def make_tar_flat(base_dir, prefix=''):
    """Create tar with files relative to base_dir"""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:gz', compresslevel=6) as tar:
        for root, dirs, files in os.walk(base_dir):
            dirs[:] = [x for x in dirs if x not in {'.git','node_modules','__pycache__','.wrangler'}]
            for fn in files:
                if fn.endswith(('.map','.log','.bak')): continue
                fp = os.path.join(root, fn)
                arcname = os.path.relpath(fp, base_dir)
                if prefix:
                    arcname = prefix + '/' + arcname
                tar.add(fp, arcname=arcname)
    buf.seek(0)
    return buf.read()

def main():
    print("=" * 60)
    print("  DEPLOY v2: Enterprise Errors + ZH + SDK v3 + Geo")
    print("=" * 60)

    # 1. Check server directory structure
    print("\n[1/7] Checking server directory structure...")
    c = new_client()
    out = run(c, 'ls -la /root/tokenpay-id/')
    print("\n  Backend dir:")
    run(c, 'ls /root/tokenpay-id/backend/ | head -10')
    print("\n  Frontend dir:")
    run(c, 'ls /root/tokenpay-id/frontend/ | head -10')
    print("\n  Frontend SDK dir:")
    run(c, 'ls /root/tokenpay-id/frontend/sdk/ 2>/dev/null || echo "no sdk dir"')
    c.close()

    # 2. Upload backend files directly via SFTP
    print("\n[2/7] Uploading backend files via SFTP...")
    c = new_client()
    sftp = c.open_sftp()
    
    # Upload server.js
    local_server = os.path.join(BACKEND, 'server.js')
    sftp.put(local_server, '/root/tokenpay-id/backend/server.js')
    print("  Uploaded server.js")
    
    # Upload email-service.js
    local_email = os.path.join(BACKEND, 'email-service.js')
    sftp.put(local_email, '/root/tokenpay-id/backend/email-service.js')
    print("  Uploaded email-service.js")
    
    sftp.close()
    c.close()

    # 3. Upload frontend files
    print("\n[3/7] Uploading frontend files via SFTP...")
    c = new_client()
    sftp = c.open_sftp()
    
    # Ensure SDK dir exists
    run(c, 'mkdir -p /root/tokenpay-id/frontend/sdk')
    
    # Upload script.js
    local_script = os.path.join(FRONTEND, 'script.js')
    sftp.put(local_script, '/root/tokenpay-id/frontend/script.js')
    print("  Uploaded script.js")
    
    # Upload SDK
    local_sdk = os.path.join(FRONTEND, 'sdk', 'tokenpay-auth.js')
    sftp.put(local_sdk, '/root/tokenpay-id/frontend/sdk/tokenpay-auth.js')
    print("  Uploaded sdk/tokenpay-auth.js")
    
    sftp.close()
    c.close()

    # 4. Verify files are in place
    print("\n[4/7] Verifying uploaded files...")
    c = new_client()
    run(c, 'head -3 /root/tokenpay-id/backend/server.js')
    run(c, 'head -3 /root/tokenpay-id/backend/email-service.js')
    run(c, 'grep "enterprise/errors" /root/tokenpay-id/backend/server.js | head -3')
    run(c, 'grep "zh:" /root/tokenpay-id/backend/email-service.js | head -1')
    run(c, 'head -3 /root/tokenpay-id/frontend/sdk/tokenpay-auth.js')
    c.close()

    # 5. Rebuild backend container
    print("\n[5/7] Rebuilding backend container...")
    c = new_client()
    run(c, 'cd /root/tokenpay-id && docker-compose up -d --build api 2>&1 | tail -15')
    c.close()
    
    print("  Waiting 12s for container to start...")
    time.sleep(12)

    # 6. Check container status
    print("\n[6/7] Checking container status...")
    c = new_client()
    out = run(c, 'docker ps --filter name=tokenpay --format "table {{.Names}}\t{{.Status}}"')

    # Reload nginx
    print("\n  Reloading nginx...")
    run(c, 'docker exec tokenpay-id-nginx nginx -s reload 2>/dev/null || echo "reload failed, restarting..."')
    c.close()

    # 7. Verify endpoints
    print("\n[7/7] Verifying endpoints...")
    time.sleep(3)
    c = new_client()

    print("\n  /health:")
    run(c, 'curl -s http://localhost:8080/health')

    print("\n  /client/preferences:")
    run(c, 'curl -s http://localhost:8080/api/v1/client/preferences')

    print("\n  /enterprise/errors (GET, no auth — expect 401):")
    out = run(c, 'curl -s http://localhost:8080/api/v1/enterprise/errors')
    
    print("\n  /enterprise/errors (POST, no auth — expect 401):")
    out = run(c, 'curl -s -X POST http://localhost:8080/api/v1/enterprise/errors -H "Content-Type: application/json" -d \'{"error_type":"test"}\'')

    print("\n  Docker logs (last 15 lines):")
    run(c, 'docker logs tokenpay-id-api --tail 15 2>&1')

    c.close()

    print("\n" + "=" * 60)
    print("  DEPLOYMENT COMPLETE")
    print("=" * 60)

if __name__ == '__main__':
    main()

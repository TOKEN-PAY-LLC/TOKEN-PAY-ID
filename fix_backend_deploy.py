#!/usr/bin/env python3
"""Debug and fix backend deployment path"""
import paramiko, tarfile, os, io, time

SERVER = "5.23.54.205"
USER = "root"
PASSWORD = "vE^6t-zFS3dpNT"
BACKEND = r"c:\Users\user\Desktop\TokenPay-Website\backend"

def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(SERVER, port=22, username=USER, password=PASSWORD,
              timeout=60, banner_timeout=60, auth_timeout=60,
              allow_agent=False, look_for_keys=False)
    return c

def run(client, cmd, show=True):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=120)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if show and out:
        for line in out.split('\n')[:50]: print("  " + line)
    if show and err:
        for line in err.split('\n')[:10]: print("  ERR: " + line)
    return out

def make_tar(source_dir):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:gz') as tar:
        for root, dirs, files in os.walk(source_dir):
            dirs[:] = [d for d in dirs if d not in ['node_modules', '.git', '__pycache__']]
            for fn in files:
                fp = os.path.join(root, fn)
                arcname = os.path.relpath(fp, source_dir)
                tar.add(fp, arcname=arcname)
    buf.seek(0)
    return buf.read()

def upload(client, data, remote_path):
    sftp = client.open_sftp()
    with sftp.open(remote_path, 'wb') as f:
        f.write(data)
    sftp.close()

client = connect()
print("Connected.\n")

# 1. Check docker-compose file and volume mounts
print("=== DOCKER COMPOSE CONFIG ===")
run(client, "cat /root/tokenpay-id/docker-compose.yml")

print("\n=== BACKEND DIR STRUCTURE ===")
run(client, "ls -la /root/tokenpay-id/backend/ | head -20")

print("\n=== CHECK server.js for check-username ===")
r = run(client, "grep -c 'check-username' /root/tokenpay-id/backend/server.js", show=False)
print(f"  check-username occurrences in server.js: {r}")

print("\n=== CHECK server.js for isValidUsername ===")
r = run(client, "grep -c 'isValidUsername' /root/tokenpay-id/backend/server.js", show=False)
print(f"  isValidUsername occurrences: {r}")

print("\n=== API CONTAINER LOGS (last 30 lines) ===")
run(client, "cd /root/tokenpay-id && docker-compose logs --tail=30 api 2>&1")

print("\n=== CHECK IF API IS RUNNING ON CORRECT PORT ===")
run(client, "docker exec tokenpay-id-api curl -s http://localhost:3000/api/v1/auth/check-username?username=test123 2>&1")

client.close()

#!/usr/bin/env python3
import paramiko, time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('5.23.54.205', username='root', password='vE^6t-zFS3dpNT', timeout=15)

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    return stdout.read().decode(), stderr.read().decode()

print("=== CONTAINERS ===")
o, e = run('docker ps --format "table {{.Names}}\\t{{.Status}}"')
print(o)

print("=== HEALTH ===")
o, e = run('docker exec tokenpay-id-api wget -qO- http://localhost:8080/health')
print(o[:300])

print("=== LOGS (last 5) ===")
o, e = run('docker logs tokenpay-id-api --tail 5 2>&1')
print((o or e)[:500])

print("=== OPENID ===")
o, e = run('curl -sk https://localhost/.well-known/openid-configuration | python3 -m json.tool 2>&1 | head -20')
print(o[:600])

print("=== SDK VERSION ===")
o, e = run('curl -sk https://localhost/api/v1/sdk/version')
print(o[:300])

ssh.close()
print("\nDONE")

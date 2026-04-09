#!/usr/bin/env python3
"""Verify deployment on tokenpay.space server"""
import paramiko, time

HOST = '5.23.54.205'
USER = 'root'
PASSWD = 'vE^6t-zFS3dpNT'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASSWD, timeout=15)

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode()
    err = stderr.read().decode()
    return out, err

# Check containers
print("=== CONTAINERS ===")
out, _ = run('docker ps --format "table {{.Names}}\\t{{.Status}}"')
print(out)

time.sleep(5)

# Check API health
print("=== API HEALTH ===")
out, err = run('docker exec tokenpay-id-api wget -qO- http://localhost:8080/health 2>&1')
print(out or err)

# Check logs
print("=== API LOGS (last 15) ===")
out, err = run('docker logs tokenpay-id-api --tail 15 2>&1')
print(out or err)

# Check OpenID discovery
print("=== OPENID DISCOVERY ===")
out, err = run('curl -sk https://localhost/.well-known/openid-configuration 2>&1 | head -5')
print(out or err)

# Check branding
print("=== BRANDING API ===")
out, err = run('curl -sk https://localhost/api/v1/oauth/branding 2>&1 | head -3')
print(out or err)

# Check SDK version
print("=== SDK VERSION ===")
out, err = run('curl -sk https://localhost/api/v1/sdk/version 2>&1')
print(out or err)

# Check widget
print("=== WIDGET FILE ===")
out, err = run('curl -sk https://localhost/sdk/tpid-widget.js 2>&1 | head -3')
print(out or err)

ssh.close()
print("\n=== VERIFY DONE ===")

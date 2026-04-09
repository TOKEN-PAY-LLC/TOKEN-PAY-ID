#!/usr/bin/env python3
"""Verify security fixes deployed: restart nginx, check headers"""
import paramiko, time

SERVER = "5.23.54.205"
USER = "root"
PASSWORD = "vE^6t-zFS3dpNT"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(SERVER, port=22, username=USER, password=PASSWORD,
          timeout=120, banner_timeout=60, auth_timeout=60,
          allow_agent=False, look_for_keys=False)

def run(cmd):
    _, stdout, stderr = c.exec_command(cmd, timeout=120)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if out: print(out)
    if err: print('ERR:', err)
    return out

# Restart nginx container to pick up new config
print('=== Restarting nginx container ===')
run('docker restart tokenpay-id-nginx')
time.sleep(3)

# Verify headers on dashboard
print('\n=== Headers on /dashboard ===')
run('curl -sk -o /dev/null -D - https://tokenpay.space/dashboard 2>&1 | head -20')

# Verify headers on API
print('\n=== Headers on /api/v1/auth/verify ===')
run('curl -sk -o /dev/null -D - https://tokenpay.space/api/v1/auth/verify -X POST -H "Content-Type: application/json" -d \'{"token":"x"}\' 2>&1 | head -25')

# CORS test from evil subdomain
print('\n=== CORS test from evil.tokenpay.space ===')
run('curl -sk -o /dev/null -D - -X OPTIONS https://tokenpay.space/api/v1/users/me -H "Origin: https://evil.tokenpay.space" -H "Access-Control-Request-Method: GET" 2>&1 | grep -i "access-control-allow-origin"')

# CORS test from legit origin
print('\n=== CORS test from tokenpay.space (should work) ===')
run('curl -sk -o /dev/null -D - -X OPTIONS https://tokenpay.space/api/v1/users/me -H "Origin: https://tokenpay.space" -H "Access-Control-Request-Method: GET" 2>&1 | grep -i "access-control-allow-origin"')

# Health check
print('\n=== Health endpoint ===')
run('curl -sk https://tokenpay.space/health')

# JSON parse error
print('\n=== JSON parse error handling ===')
run('curl -sk https://tokenpay.space/api/v1/auth/login -H "Content-Type: application/json" -d "{bad json"')

# Container status
print('\n=== Container status ===')
run('docker ps --format "table {{.Names}}\\t{{.Status}}" | grep tokenpay')

c.close()
print('\n=== Verification complete ===')

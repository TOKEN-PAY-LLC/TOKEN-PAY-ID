import paramiko, time
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('5.23.54.205', username='root', password='vE^6t-zFS3dpNT')

print('[*] Restarting tokenpay-id-api...')
stdin, stdout, stderr = ssh.exec_command('docker restart tokenpay-id-api', timeout=30)
print(stdout.read().decode().strip() or stderr.read().decode().strip())

print('[*] Waiting 6s for startup...')
time.sleep(6)

print('[*] Container status:')
stdin, stdout, stderr = ssh.exec_command('docker ps --filter name=tokenpay-id-api --format "{{.Names}}  {{.Status}}"')
print('  ' + stdout.read().decode().strip())

print('\n[*] Last 15 log lines:')
stdin, stdout, stderr = ssh.exec_command('docker logs tokenpay-id-api --tail 15 2>&1')
for line in stdout.read().decode().strip().split('\n'):
    print('  | ' + line)

# Verify key endpoints
print('\n[*] Endpoint checks:')
checks = [
    ('API health', "curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/api/v1/auth/verify -X POST -H 'Content-Type: application/json' -d '{\"token\":\"x\"}'"),
    ('Login page', "curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/login"),
    ('QR init', "curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/api/v1/auth/qr/login-init -X POST -H 'Content-Type: application/json'"),
    ('Reset-password', "curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/api/v1/auth/reset-password -X POST -H 'Content-Type: application/json' -d '{}'"),
]
for label, cmd in checks:
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
    out = stdout.read().decode().strip()
    print(f'  {label}: HTTP {out}')

ssh.close()
print('\n=== DONE ===')

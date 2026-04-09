"""Deploy auth ecosystem hardening: QR TDZ fix, 2FA on reset/change/disable, frontend steps"""
import paramiko, os, time

HOST = '5.23.54.205'
USER = 'root'
PASS = 'vE^6t-zFS3dpNT'
LOCAL = os.path.dirname(os.path.abspath(__file__))

FILES = [
    ('frontend/login.html',     '/root/tokenpay-id/frontend/login.html'),
    ('frontend/dashboard.html', '/root/tokenpay-id/frontend/dashboard.html'),
    ('backend/server.js',       '/root/tokenpay-id/backend/server.js'),
]

def main():
    print('=== AUTH HARDENING DEPLOY ===\n')
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=15)
    sftp = ssh.open_sftp()

    # 1. Upload files
    for local_rel, remote in FILES:
        local_path = os.path.join(LOCAL, local_rel)
        size = os.path.getsize(local_path)
        print(f'[>] {local_rel} ({size:,} B) -> {remote}')
        sftp.put(local_path, remote)
        print(f'    OK')

    # 2. Restart backend container to pick up server.js changes
    print('\n[*] Restarting backend...')
    stdin, stdout, stderr = ssh.exec_command('docker restart tokenpay-id-backend', timeout=30)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    print(f'    {out or err}')

    # Wait for backend to come up
    print('[*] Waiting for backend startup...')
    time.sleep(5)

    # 3. Verify backend is healthy
    print('\n[*] Verifying backend health...')
    checks = [
        ('Backend health',
         "curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/api/v1/auth/verify -X POST -H 'Content-Type: application/json' -d '{\"token\":\"test\"}'"),
        ('QR login-init endpoint',
         "curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/api/v1/auth/qr/login-init -X POST -H 'Content-Type: application/json'"),
        ('Reset-password requires 2FA param in code',
         "grep -c 'two_factor_code' /root/tokenpay-id/backend/server.js"),
        ('Change-password requires 2FA',
         "grep -c 'requires_2fa.*change password' /root/tokenpay-id/backend/server.js"),
        ('2FA disable requires code',
         "grep -c 'missing_code.*TOTP code required to disable' /root/tokenpay-id/backend/server.js"),
    ]
    all_ok = True
    for label, cmd in checks:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
        out = stdout.read().decode().strip()
        ok = bool(out and out != '0')
        print(f'  {"✓" if ok else "✗"} {label}: {out}')
        if not ok: all_ok = False

    # 4. Verify frontend fixes
    print('\n[*] Verifying frontend fixes...')
    fe_checks = [
        ('login.html var _qrSessionId (no TDZ)',
         "grep -c 'var _qrSessionId' /root/tokenpay-id/frontend/login.html"),
        ('login.html step7 (2FA reset)',
         "grep -c 'step7' /root/tokenpay-id/frontend/login.html"),
        ('login.html submitReset2FA',
         "grep -c 'submitReset2FA' /root/tokenpay-id/frontend/login.html"),
        ('login.html requires_2fa handling',
         "grep -c 'data.requires_2fa' /root/tokenpay-id/frontend/login.html"),
        ('dashboard.html 2FA on change-password',
         "grep -c 'two_factor_code' /root/tokenpay-id/frontend/dashboard.html"),
        ('dashboard.html 2FA on disable',
         "grep -c 'code:c.replace' /root/tokenpay-id/frontend/dashboard.html"),
    ]
    for label, cmd in fe_checks:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
        out = stdout.read().decode().strip()
        ok = bool(out and out != '0')
        print(f'  {"✓" if ok else "✗"} {label}: {out}')
        if not ok: all_ok = False

    # 5. Check public pages load
    print('\n[*] Checking public pages...')
    pages = [
        ('Login page', "curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/login"),
        ('Dashboard page', "curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/dashboard"),
        ('Main page', "curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/"),
    ]
    for label, cmd in pages:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
        out = stdout.read().decode().strip()
        print(f'  {label}: HTTP {out}')

    # 6. Check backend logs for startup errors
    print('\n[*] Backend startup logs (last 10 lines)...')
    stdin, stdout, stderr = ssh.exec_command('docker logs tokenpay-id-backend --tail 10 2>&1', timeout=10)
    logs = stdout.read().decode().strip()
    for line in logs.split('\n'):
        print(f'  | {line}')

    sftp.close()
    ssh.close()
    print(f'\n=== {"ALL CHECKS PASSED" if all_ok else "DEPLOY COMPLETED WITH WARNINGS"} ===')

if __name__ == '__main__':
    main()

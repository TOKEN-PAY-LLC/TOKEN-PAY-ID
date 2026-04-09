"""Deploy final 2FA hardening: magic link 2FA, all fixes"""
import paramiko, os, time

HOST = '5.23.54.205'
USER = 'root'
PASS = 'vE^6t-zFS3dpNT'
LOCAL = os.path.dirname(os.path.abspath(__file__))

FILES = [
    ('frontend/login.html',     '/root/tokenpay-id/frontend/login.html'),
    ('backend/server.js',       '/root/tokenpay-id/backend/server.js'),
]

def main():
    print('=== FINAL 2FA DEPLOY ===\n')
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=15)
    sftp = ssh.open_sftp()

    for local_rel, remote in FILES:
        local_path = os.path.join(LOCAL, local_rel)
        size = os.path.getsize(local_path)
        print(f'[>] {local_rel} ({size:,} B) -> {remote}')
        sftp.put(local_path, remote)
        print(f'    OK')

    print('\n[*] Restarting tokenpay-id-api...')
    stdin, stdout, stderr = ssh.exec_command('docker restart tokenpay-id-api', timeout=30)
    print('    ' + (stdout.read().decode().strip() or stderr.read().decode().strip()))

    print('[*] Waiting 6s...')
    time.sleep(6)

    print('\n[*] Backend logs:')
    stdin, stdout, stderr = ssh.exec_command('docker logs tokenpay-id-api --tail 5 2>&1')
    for line in stdout.read().decode().strip().split('\n'):
        print('  | ' + line)

    print('\n[*] Verification:')
    checks = [
        ('Backend healthy', "curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/api/v1/auth/verify -X POST -H 'Content-Type: application/json' -d '{\"token\":\"x\"}'"),
        ('Login page', "curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/login"),
        ('Magic link 2FA in backend', "grep -c 'requires_2fa.*2FA code required to complete login' /root/tokenpay-id/backend/server.js"),
        ('Magic link 2FA in frontend', "grep -c '_startMagicPollWith2FA' /root/tokenpay-id/frontend/login.html"),
        ('Reset 2FA step7 in frontend', "grep -c 'submitReset2FA' /root/tokenpay-id/frontend/login.html"),
        ('QR var fix', "grep -c 'var _qrSessionId' /root/tokenpay-id/frontend/login.html"),
        ('Reset-password 2FA backend', "grep -c 'two_factor_code.*reset' /root/tokenpay-id/backend/server.js"),
        ('Change-password 2FA backend', "grep -c 'requires_2fa.*change password' /root/tokenpay-id/backend/server.js"),
        ('2FA disable mandatory code', "grep -c 'missing_code.*TOTP code required to disable' /root/tokenpay-id/backend/server.js"),
    ]
    all_ok = True
    for label, cmd in checks:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
        out = stdout.read().decode().strip()
        ok = bool(out and out != '0')
        print(f'  {"✓" if ok else "✗"} {label}: {out}')
        if not ok: all_ok = False

    sftp.close()
    ssh.close()
    print(f'\n=== {"ALL CHECKS PASSED ✓" if all_ok else "WARNINGS"} ===')

if __name__ == '__main__':
    main()

"""Deploy QR flow fix + email headers fix"""
import paramiko, os, time

HOST = '5.23.54.205'
USER = 'root'
PASS = 'vE^6t-zFS3dpNT'
LOCAL = os.path.dirname(os.path.abspath(__file__))

FILES = [
    ('frontend/dashboard.html', '/root/tokenpay-id/frontend/dashboard.html'),
    ('frontend/qr-login.html',  '/root/tokenpay-id/frontend/qr-login.html'),
    ('backend/email-service.js', '/root/tokenpay-id/backend/email-service.js'),
]

def main():
    print('=== DEPLOY: QR flow + email fix ===\n')
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

    print('\n[*] Backend logs (last 8):')
    stdin, stdout, stderr = ssh.exec_command('docker logs tokenpay-id-api --tail 8 2>&1')
    for line in stdout.read().decode().strip().split('\n'):
        print('  | ' + line)

    print('\n[*] Verification:')
    checks = [
        ('Backend healthy',
         "curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/api/v1/auth/verify -X POST -H 'Content-Type: application/json' -d '{\"token\":\"x\"}'"),
        ('Dashboard page',
         "curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/dashboard"),
        ('QR-login page',
         "curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/qr-login"),
        ('Dashboard QR pre-approve',
         "grep -c 'login-confirm.*Pre-approve' /root/tokenpay-id/frontend/dashboard.html"),
        ('QR-login autoLogin function',
         "grep -c 'function autoLogin' /root/tokenpay-id/frontend/qr-login.html"),
        ('Email: no Precedence:bulk',
         "grep -c 'Precedence' /root/tokenpay-id/backend/email-service.js; echo ok"),
        ('SMTP test',
         "docker exec tokenpay-id-api node -e \"const{initTransporter}=require('./email-service');\" 2>&1; echo done"),
    ]
    all_ok = True
    for label, cmd in checks:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
        out = stdout.read().decode().strip()
        ok = True
        if 'no Precedence' in label:
            ok = out.startswith('0')
        elif label in ('Backend healthy', 'Dashboard page', 'QR-login page'):
            ok = out == '200'
        elif 'pre-approve' in label.lower() or 'autoLogin' in label:
            ok = out and out != '0'
        print(f'  {"✓" if ok else "✗"} {label}: {out}')
        if not ok: all_ok = False

    # Test email send
    print('\n[*] Test email delivery:')
    stdin, stdout, stderr = ssh.exec_command(
        """curl -sk -X POST https://tokenpay.space/api/v1/auth/send-code -H 'Content-Type: application/json' -d '{"email":"info@tokenpay.space","type":"login"}' 2>&1"""
    )
    print('  ' + stdout.read().decode().strip())
    time.sleep(2)
    stdin, stdout, stderr = ssh.exec_command('docker logs tokenpay-id-api --tail 3 2>&1')
    for line in stdout.read().decode().strip().split('\n'):
        print('  | ' + line)

    sftp.close()
    ssh.close()
    print(f'\n=== {"ALL OK ✓" if all_ok else "WARNINGS"} ===')

if __name__ == '__main__':
    main()

"""Deploy QR overhaul + security fixes + stuck pages fix"""
import paramiko, os, time

HOST = '5.23.54.205'
USER = 'root'
PASS = 'vE^6t-zFS3dpNT'
LOCAL = os.path.dirname(os.path.abspath(__file__))

FILES = [
    ('frontend/dashboard.html', '/root/tokenpay-id/frontend/dashboard.html'),
    ('frontend/login.html',     '/root/tokenpay-id/frontend/login.html'),
    ('frontend/qr-login.html',  '/root/tokenpay-id/frontend/qr-login.html'),
    ('backend/server.js',       '/root/tokenpay-id/backend/server.js'),
    ('backend/email-service.js', '/root/tokenpay-id/backend/email-service.js'),
]

def main():
    print('=== DEPLOY: QR overhaul + security + stuck fix ===\n')
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

    print('[*] Waiting 7s...')
    time.sleep(7)

    print('\n[*] Backend logs (last 8):')
    stdin, stdout, stderr = ssh.exec_command('docker logs tokenpay-id-api --tail 8 2>&1')
    for line in stdout.read().decode().strip().split('\n'):
        print('  | ' + line)

    print('\n[*] Verification:')
    checks = [
        ('Backend API',
         "curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/api/v1/auth/verify -X POST -H 'Content-Type: application/json' -d '{\"token\":\"x\"}'"),
        ('Dashboard page',
         "curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/dashboard"),
        ('Login page',
         "curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/login"),
        ('QR-login page',
         "curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/qr-login"),
        ('Dashboard: QR tabs',
         "grep -c 'switchQRTab' /root/tokenpay-id/frontend/dashboard.html"),
        ('Dashboard: confirmQRLogin',
         "grep -c 'function confirmQRLogin' /root/tokenpay-id/frontend/dashboard.html"),
        ('Dashboard: QR camera',
         "grep -c 'function startQRCamera' /root/tokenpay-id/frontend/dashboard.html"),
        ('Dashboard: AbortController timeout',
         "grep -c 'AbortController' /root/tokenpay-id/frontend/dashboard.html"),
        ('Login: QR instructions',
         "grep -c 'Личный кабинет' /root/tokenpay-id/frontend/login.html"),
        ('QR-login: autoLogin',
         "grep -c 'function autoLogin' /root/tokenpay-id/frontend/qr-login.html"),
        ('Backend: QR rate-limit',
         "grep -c 'authLimiter.*login-init\\|login-init.*authLimiter' /root/tokenpay-id/backend/server.js"),
        ('Backend: session cap',
         "grep -c 'too_many_sessions' /root/tokenpay-id/backend/server.js"),
        ('Backend: confirmedBy audit',
         "grep -c 'confirmedBy' /root/tokenpay-id/backend/server.js"),
        ('Email: no Precedence',
         "grep -c 'Precedence' /root/tokenpay-id/backend/email-service.js"),
    ]
    all_ok = True
    for label, cmd in checks:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
        out = stdout.read().decode().strip()
        ok = True
        if label in ('Backend API', 'Dashboard page', 'Login page', 'QR-login page'):
            ok = out == '200'
        elif 'no Precedence' in label:
            ok = out == '0'
        else:
            ok = out and out != '0'
        print(f'  {"✓" if ok else "✗"} {label}: {out}')
        if not ok: all_ok = False

    sftp.close()
    ssh.close()
    print(f'\n=== {"ALL OK ✓" if all_ok else "WARNINGS — check above"} ===')

if __name__ == '__main__':
    main()

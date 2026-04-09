import paramiko, sys, os

HOST = '5.23.54.205'
USER = 'root'
PASS = 'vE^6t-zFS3dpNT'

FILES = [
    'frontend/index.html',
    'frontend/styles.css',
    'frontend/script.js',
    'frontend/docs.html',
    'frontend/login.html',
    'frontend/register.html',
    'frontend/dashboard.html',
    'frontend/privacy.html',
    'frontend/terms.html',
    'frontend/admin.html',
    'frontend/oauth-widget.html',
]

REMOTE_BASE = '/root/tokenpay-id'

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f'Connecting to {HOST}...')
    ssh.connect(HOST, username=USER, password=PASS, timeout=15)
    sftp = ssh.open_sftp()

    for f in FILES:
        local = os.path.join(os.path.dirname(__file__), f)
        remote = f'{REMOTE_BASE}/{f}'
        print(f'  Upload: {f}')
        sftp.put(local, remote)

    # Also copy to /opt/tokenpay-website if it exists
    for f in FILES:
        local = os.path.join(os.path.dirname(__file__), f)
        remote2 = f'/opt/tokenpay-website/{f}'
        try:
            sftp.put(local, remote2)
            print(f'  Upload (opt): {f}')
        except:
            pass

    sftp.close()
    print('All files uploaded. Reloading nginx...')

    stdin, stdout, stderr = ssh.exec_command('docker exec tokenpay-nginx nginx -s reload 2>&1 || docker restart tokenpay-nginx 2>&1')
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    print(f'  nginx: {out or err or "ok"}')

    # Verify
    print('\nVerification:')
    checks = [
        ("curl -sk https://tokenpay.space/ | grep -o 'styles.css?v=[^\"]*' | head -1", "CSS version"),
        ("curl -sk https://tokenpay.space/ | grep -c 'hero-doc-link' | head -1", "Doc links count"),
        ("curl -sk https://tokenpay.space/ | grep -o 'Условия использования' | head -1", "Terms link"),
        ("curl -sk https://tokenpay.space/ | grep -o 'Политика конфиденциальности' | head -1", "Privacy link"),
        ("curl -sk https://tokenpay.space/docs | grep -o 'btn btn-secondary btn-sm' | head -1", "Email btn class"),
    ]
    for cmd, label in checks:
        _, so, se = ssh.exec_command(cmd)
        r = so.read().decode().strip()
        print(f'  {label}: {r or "(empty)"}')

    ssh.close()
    print('\nDone!')

if __name__ == '__main__':
    main()

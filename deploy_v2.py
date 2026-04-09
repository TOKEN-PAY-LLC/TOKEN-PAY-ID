import paramiko, os

HOST = '5.23.54.205'
USER = 'root'
PASS = 'vE^6t-zFS3dpNT'
LOCAL_BASE = os.path.dirname(__file__)
REMOTE_BASES = ['/root/tokenpay-id', '/opt/tokenpay-website']

FILES = [
    'frontend/styles.css',
    'frontend/index.html',
    'frontend/login.html',
    'frontend/register.html',
    'frontend/dashboard.html',
    'frontend/docs.html',
    'frontend/privacy.html',
    'frontend/terms.html',
    'frontend/admin.html',
    'frontend/oauth-widget.html',
]

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f'Connecting to {HOST}...')
    ssh.connect(HOST, username=USER, password=PASS, timeout=15)
    sftp = ssh.open_sftp()

    for rb in REMOTE_BASES:
        for f in FILES:
            local = os.path.join(LOCAL_BASE, f)
            remote = f'{rb}/{f}'
            try:
                sftp.put(local, remote)
                print(f'  OK: {rb}/{f}')
            except Exception as e:
                print(f'  SKIP: {rb}/{f} ({e})')

    sftp.close()

    # Reload nginx
    print('\nReloading nginx...')
    _, so, se = ssh.exec_command('docker exec tokenpay-id-nginx nginx -s reload 2>&1')
    print(so.read().decode().strip() or 'ok')

    # Verify
    print('\nVerification:')
    checks = [
        ("curl -sk https://tokenpay.space/ | grep -o 'styles.css?v=[^\"]*' | head -1", "CSS ver (index)"),
        ("curl -sk https://tokenpay.space/login | grep -o 'styles.css?v=[^\"]*' | head -1", "CSS ver (login)"),
        ("curl -sk https://tokenpay.space/styles.css | grep -c 'LIGHT THEME V2'", "Light theme V2 rules"),
        ("curl -sk https://tokenpay.space/styles.css | grep -c 'auth-page'", "Auth page rules"),
        ("curl -sk https://tokenpay.space/styles.css | grep -o 'logoPulseLight' | head -1", "Logo pulse light anim"),
        ("curl -sk https://tokenpay.space/styles.css | grep -o 'background-attachment:fixed' | head -1", "BG attachment"),
    ]
    for cmd, label in checks:
        _, so, _ = ssh.exec_command(cmd)
        r = so.read().decode().strip()
        status = '✓' if r and r != '0' else '✗'
        print(f'  {status} {label}: {r}')

    # Also check GitHub for contributor
    print('\nChecking git config...')
    _, so, _ = ssh.exec_command('cd /root/tokenpay-id && git log --format="%an <%ae>" | sort -u | head -20 2>/dev/null; echo "---"; cd /root/tokenpay-id && git remote -v 2>/dev/null | head -5')
    print(so.read().decode().strip())

    ssh.close()
    print('\nDone!')

if __name__ == '__main__':
    main()

"""Deploy SDK v2.0, Widget v1.2, updated docs and index.html to production Docker containers"""
import paramiko, os, sys

HOST = '5.23.54.205'
USER = 'root'
PASS = 'vE^6t-zFS3dpNT'
LOCAL_BASE = os.path.dirname(os.path.abspath(__file__))

FILES = [
    ('frontend/index.html', '/root/tokenpay-id/frontend/index.html'),
    ('frontend/docs.html', '/root/tokenpay-id/frontend/docs.html'),
    ('frontend/sdk/tokenpay-auth.js', '/root/tokenpay-id/frontend/sdk/tokenpay-auth.js'),
    ('frontend/sdk/tpid-widget.js', '/root/tokenpay-id/frontend/sdk/tpid-widget.js'),
]

def main():
    print('=== TOKEN PAY ID — SDK & Docs Deploy ===')
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=15)
    sftp = ssh.open_sftp()

    # Ensure sdk directory exists on server
    try:
        sftp.stat('/root/tokenpay-id/frontend/sdk')
    except FileNotFoundError:
        print('[+] Creating /root/tokenpay-id/frontend/sdk/')
        ssh.exec_command('mkdir -p /root/tokenpay-id/frontend/sdk')
        import time; time.sleep(1)

    # Upload files
    for local_rel, remote_path in FILES:
        local_path = os.path.join(LOCAL_BASE, local_rel)
        if not os.path.exists(local_path):
            print(f'[!] SKIP (not found): {local_rel}')
            continue
        size = os.path.getsize(local_path)
        print(f'[>] {local_rel} ({size:,} bytes) -> {remote_path}')
        sftp.put(local_path, remote_path)
        print(f'    OK')

    # Copy files into Docker nginx container
    print('\n[*] Copying to Docker nginx container...')
    docker_cmds = [
        'docker cp /root/tokenpay-id/frontend/index.html tokenpay-id-nginx:/usr/share/nginx/html/index.html',
        'docker cp /root/tokenpay-id/frontend/docs.html tokenpay-id-nginx:/usr/share/nginx/html/docs.html',
        'docker exec tokenpay-id-nginx mkdir -p /usr/share/nginx/html/sdk',
        'docker cp /root/tokenpay-id/frontend/sdk/tokenpay-auth.js tokenpay-id-nginx:/usr/share/nginx/html/sdk/tokenpay-auth.js',
        'docker cp /root/tokenpay-id/frontend/sdk/tpid-widget.js tokenpay-id-nginx:/usr/share/nginx/html/sdk/tpid-widget.js',
    ]
    for cmd in docker_cmds:
        print(f'  $ {cmd}')
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        if out: print(f'    {out}')
        if err: print(f'    ERR: {err}')

    # Verify deployment
    print('\n[*] Verifying...')
    verify_cmds = [
        ('docs.html v2.2', "docker exec tokenpay-id-nginx head -c 500 /usr/share/nginx/html/docs.html | grep -o 'v2\\.2'"),
        ('SDK v2.0', "docker exec tokenpay-id-nginx head -c 200 /usr/share/nginx/html/sdk/tokenpay-auth.js | grep -o 'v2\\.0'"),
        ('Widget v1.2', "docker exec tokenpay-id-nginx head -c 200 /usr/share/nginx/html/sdk/tpid-widget.js | grep -o 'v1\\.2'"),
        ('PKCE in SDK', "docker exec tokenpay-id-nginx grep -c 'code_challenge' /usr/share/nginx/html/sdk/tokenpay-auth.js"),
        ('index.html no <br> in h2', "docker exec tokenpay-id-nginx grep -c 'цифровой идентификатор</h2>' /usr/share/nginx/html/index.html"),
    ]
    all_ok = True
    for label, cmd in verify_cmds:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
        out = stdout.read().decode().strip()
        ok = bool(out and out != '0')
        print(f'  {"✓" if ok else "✗"} {label}: {out}')
        if not ok: all_ok = False

    # Check public URLs
    print('\n[*] Checking public endpoints...')
    pub_checks = [
        ('SDK public', "curl -s -o /dev/null -w '%{http_code}' https://tokenpay.space/sdk/tokenpay-auth.js"),
        ('Widget public', "curl -s -o /dev/null -w '%{http_code}' https://tokenpay.space/sdk/tpid-widget.js"),
        ('Docs public', "curl -s -o /dev/null -w '%{http_code}' https://tokenpay.space/docs"),
    ]
    for label, cmd in pub_checks:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
        out = stdout.read().decode().strip()
        print(f'  {label}: HTTP {out}')

    sftp.close()
    ssh.close()

    if all_ok:
        print('\n=== DEPLOY SUCCESS ===')
    else:
        print('\n=== DEPLOY COMPLETED WITH WARNINGS ===')

if __name__ == '__main__':
    main()

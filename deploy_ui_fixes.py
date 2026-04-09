#!/usr/bin/env python3
"""Deploy UI/UX fixes to production via Paramiko (SFTP)."""
import paramiko
import os
import sys

HOST = '5.23.54.205'
USER = 'root'
REMOTE_BASE = '/root/tokenpay-id/frontend'
LOCAL_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frontend')

FILES = [
    'styles.css',
    'index.html',
    'login.html',
    'register.html',
    'dashboard.html',
    'admin.html',
    'qr-login.html',
    'captcha.js',
    'tpid-widget.js',
    'oauth-widget.js',
    'sdk/tokenpay-auth.js',
    'sdk/tpid-widget.js',
]

def load_key(path, passphrase):
    """Try multiple key formats for OpenSSH private keys."""
    pw = passphrase if passphrase else None
    errors = []
    for cls_name, cls in [('RSA', paramiko.RSAKey), ('Ed25519', paramiko.Ed25519Key), ('ECDSA', paramiko.ECDSAKey)]:
        try:
            return cls.from_private_key_file(path, password=pw)
        except Exception as e:
            errors.append(f'  {cls_name}: {e}')
    print('[!] All key types failed:')
    for err in errors:
        print(err)
    raise Exception(f'Cannot load key from {path}')

PASSWORD = 'vE^6t-zFS3dpNT'

def main():
    print(f'[*] Connecting to {HOST}...')
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=22, username=USER, password=PASSWORD,
                timeout=30, banner_timeout=30, auth_timeout=30,
                allow_agent=False, look_for_keys=False)
    sftp = ssh.open_sftp()
    print('[+] Connected!')

    # Ensure sdk dir exists
    try:
        sftp.stat(REMOTE_BASE + '/sdk')
    except FileNotFoundError:
        sftp.mkdir(REMOTE_BASE + '/sdk')

    for fname in FILES:
        local = os.path.join(LOCAL_BASE, fname.replace('/', os.sep))
        remote = REMOTE_BASE + '/' + fname
        if not os.path.exists(local):
            print(f'  [!] SKIP (not found): {local}')
            continue
        size = os.path.getsize(local)
        sftp.put(local, remote)
        print(f'  [+] {fname} ({size:,} bytes)')

    # Also copy to /var/www/frontend if it exists (host process path)
    print('\n[*] Syncing to /var/www/frontend...')
    stdin, stdout, stderr = ssh.exec_command('cp -r /root/tokenpay-id/frontend/* /var/www/frontend/ 2>/dev/null; echo OK')
    print('  ', stdout.read().decode().strip())

    print('[*] Finding nginx service name...')
    stdin, stdout, stderr = ssh.exec_command('cd /root/tokenpay-id && docker compose ps --format "{{.Service}}"')
    services = stdout.read().decode().strip()
    print(f'  Services: {services}')
    
    nginx_svc = None
    for svc in services.splitlines():
        if 'nginx' in svc.lower():
            nginx_svc = svc.strip()
            break
    
    if nginx_svc:
        print(f'[*] Restarting {nginx_svc}...')
        stdin, stdout, stderr = ssh.exec_command(f'cd /root/tokenpay-id && docker compose restart {nginx_svc}')
        print(stdout.read().decode())
        err = stderr.read().decode()
        if err:
            print(err)
    else:
        print('[*] No nginx service found, trying generic restart...')
        stdin, stdout, stderr = ssh.exec_command('cd /root/tokenpay-id && docker compose restart')
        print(stdout.read().decode())
        print(stderr.read().decode())

    print('[+] Deploy complete!')
    sftp.close()
    ssh.close()

if __name__ == '__main__':
    main()

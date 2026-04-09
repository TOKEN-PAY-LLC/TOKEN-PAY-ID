#!/usr/bin/env python3
"""Deploy ALL fixes: favicons, icons, HTML, email-service to production."""
import paramiko
import os

HOST = '5.23.54.205'
USER = 'root'
PASSWORD = 'vE^6t-zFS3dpNT'
LOCAL_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)))
REMOTE_FE = '/root/tokenpay-id/frontend'
REMOTE_BE = '/root/tokenpay-id/backend'

# Frontend files to deploy
FE_FILES = [
    # Icons & favicons
    'favicon.ico', 'favicon.svg', 'icon-192.png', 'icon-512.png',
    'apple-touch-icon.png', 'tokenpay-icon.png',
    'email-avatar.png', 'og-image.png', 'tpid-logo-white.png',
    'bimi-logo.svg',
    # HTML (all updated with v=6)
    'index.html', 'login.html', 'register.html', 'dashboard.html',
    'admin.html', 'qr-login.html', 'docs.html', 'privacy.html',
    'terms.html', 'welcome.html', 'oauth-consent.html', 'oauth-widget.html',
    # CSS/JS
    'styles.css', 'captcha.js', 'tpid-widget.js', 'oauth-widget.js',
    # SDK
    'sdk/tokenpay-auth.js', 'sdk/tpid-widget.js',
]

# Backend files
BE_FILES = [
    'email-service.js',
]

def main():
    print(f'[*] Connecting to {HOST}...')
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=22, username=USER, password=PASSWORD,
                timeout=30, banner_timeout=30, auth_timeout=30,
                allow_agent=False, look_for_keys=False)
    sftp = ssh.open_sftp()
    print('[+] Connected!\n')

    # Deploy frontend
    print('=== FRONTEND ===')
    for fname in FE_FILES:
        local = os.path.join(LOCAL_BASE, 'frontend', fname.replace('/', os.sep))
        remote = REMOTE_FE + '/' + fname
        if not os.path.exists(local):
            print(f'  [!] SKIP: {fname}')
            continue
        sftp.put(local, remote)
        sz = os.path.getsize(local)
        print(f'  [+] {fname} ({sz:,} bytes)')

    # Deploy backend
    print('\n=== BACKEND ===')
    for fname in BE_FILES:
        local = os.path.join(LOCAL_BASE, 'backend', fname.replace('/', os.sep))
        remote = REMOTE_BE + '/' + fname
        if not os.path.exists(local):
            print(f'  [!] SKIP: {fname}')
            continue
        sftp.put(local, remote)
        sz = os.path.getsize(local)
        print(f'  [+] {fname} ({sz:,} bytes)')

    # Sync to /var/www paths
    print('\n=== SYNC TO /var/www ===')
    ssh.exec_command('cp -r /root/tokenpay-id/frontend/* /var/www/frontend/ 2>/dev/null')
    ssh.exec_command('cp /root/tokenpay-id/backend/email-service.js /var/www/backend/email-service.js 2>/dev/null')
    print('  [+] Synced')

    # Check current SMTP env vars
    print('\n=== CHECKING SMTP CONFIG ===')
    stdin, stdout, stderr = ssh.exec_command('grep -i smtp /root/tokenpay-id/.env 2>/dev/null || echo "no .env"')
    env_out = stdout.read().decode().strip()
    print(f'  Docker .env: {env_out}')
    
    stdin, stdout, stderr = ssh.exec_command('grep -i smtp /var/www/backend/.env 2>/dev/null || echo "no .env"')
    env_out2 = stdout.read().decode().strip()
    print(f'  Host .env: {env_out2}')

    # Restart services
    print('\n=== RESTARTING SERVICES ===')
    
    # Docker containers
    stdin, stdout, stderr = ssh.exec_command('cd /root/tokenpay-id && docker compose restart')
    out = stdout.read().decode()
    err = stderr.read().decode()
    print(f'  Docker: {err.strip()}')

    # PM2 host process
    stdin, stdout, stderr = ssh.exec_command('pm2 restart all 2>/dev/null || echo "no pm2"')
    out = stdout.read().decode().strip()
    print(f'  PM2: {out[:200]}')

    # Purge CF cache
    print('\n=== PURGING CLOUDFLARE CACHE ===')
    import requests
    r = requests.post(
        'https://api.cloudflare.com/client/v4/zones/210a25c077c2bfdc43a853762ccb358d/purge_cache',
        headers={
            'X-Auth-Email': 'ichernykh08@gmail.com',
            'X-Auth-Key': '5a4a5eddcb5882e068e0c407b670df0ef65ac',
            'Content-Type': 'application/json'
        },
        json={'purge_everything': True}
    )
    d = r.json()
    print(f'  [{"+" if d.get("success") else "!"}] Cache purge: {d.get("success")}')

    print('\n[+] DEPLOY COMPLETE!')
    sftp.close()
    ssh.close()

if __name__ == '__main__':
    main()

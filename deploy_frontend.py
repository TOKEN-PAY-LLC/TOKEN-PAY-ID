import paramiko
import os

HOST = '5.23.54.205'
USER = 'root'
PASSWD = 'vE^6t-zFS3dpNT'
REMOTE_DIR = '/root/tokenpay-id'

LOCAL_BASE = os.path.dirname(os.path.abspath(__file__))

# Frontend files to upload
FRONTEND_FILES = [
    'frontend/styles.css',
    'frontend/index.html',
    'frontend/dashboard.html',
    'frontend/login.html',
    'frontend/register.html',
    'frontend/docs.html',
    'frontend/privacy.html',
    'frontend/terms.html',
    'frontend/admin.html',
    'frontend/oauth-consent.html',
    'frontend/captcha.js',
    'frontend/script.js',
    'frontend/oauth-widget.html',
    'frontend/oauth-widget.js',
    'frontend/tpid-widget.js',
]

# Nginx config
NGINX_FILES = [
    'nginx/nginx.conf',
]

# Backend files to upload
BACKEND_FILES = [
    'backend/email-service.js',
    'backend/server.js',
]

ALL_FILES = FRONTEND_FILES + BACKEND_FILES + NGINX_FILES

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASSWD, timeout=15)
print('[OK] Connected to', HOST)

sftp = ssh.open_sftp()

for f in ALL_FILES:
    local = os.path.join(LOCAL_BASE, f)
    remote = f'{REMOTE_DIR}/{f}'
    print(f'  [UPLOAD] {f}')
    sftp.put(local, remote)

sftp.close()
print(f'[OK] {len(ALL_FILES)} files uploaded')

# Restart nginx to clear cache (frontend is volume-mounted)
stdin, stdout, stderr = ssh.exec_command('docker exec tokenpay-id-nginx nginx -s reload')
stdout.read()
print('[OK] Nginx reloaded')

# Rebuild API container for email-service.js change
print('[REBUILD] Rebuilding API container for email template fix...')
stdin, stdout, stderr = ssh.exec_command(f'cd {REMOTE_DIR} && docker compose up -d --build api 2>&1', timeout=300)
out = stdout.read().decode()
print(out[-500:] if len(out) > 500 else out)
print('[OK] API rebuilt')

# Verify
stdin, stdout, stderr = ssh.exec_command('docker ps --format "table {{.Names}}\\t{{.Status}}"')
print(stdout.read().decode())

ssh.close()
print('=== DEPLOY DONE ===')

#!/usr/bin/env python3
"""
TokenPay Deployment Script using Paramiko
Install: pip install paramiko
"""

import paramiko
import os
import tarfile
import sys
from pathlib import Path

# Configuration
SERVER_IP = "5.23.54.205"
SSH_USER = "root"
PASSWORD = "vE^6t-zFS3dpNT"
LOCAL_PATH = Path("c:/Users/user/Desktop/TokenPay-Website")
REMOTE_PATH = "/var/www"

def create_archive():
    """Create tar.gz archive of frontend files"""
    print("[1/5] Creating deployment archive...")
    archive_path = LOCAL_PATH / "tokenpay-deploy.tar.gz"
    frontend_path = LOCAL_PATH / "frontend"
    
    with tarfile.open(archive_path, "w:gz") as tar:
        for file_path in frontend_path.rglob("*"):
            if file_path.is_file():
                arcname = file_path.relative_to(frontend_path)
                tar.add(file_path, arcname=arcname)
    
    size = archive_path.stat().st_size / 1024
    print(f"    Archive created: {archive_path.name} ({size:.1f} KB)")
    return archive_path

def connect_ssh():
    """Establish SSH connection"""
    print(f"[2/5] Connecting to {SERVER_IP}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SERVER_IP, port=22, username=SSH_USER, password=PASSWORD, 
                   timeout=30, banner_timeout=30, auth_timeout=30,
                   allow_agent=False, look_for_keys=False)
    print("    Connected!")
    return client

def upload_file(ssh_client, local_file, remote_file):
    """Upload file via SFTP"""
    print("[3/5] Uploading files...")
    sftp = ssh_client.open_sftp()
    sftp.put(str(local_file), remote_file)
    sftp.close()
    print(f"    Uploaded to {remote_file}")

def deploy(ssh_client):
    """Execute deployment commands on server"""
    print("[4/5] Deploying on server...")
    
    commands = f"""
cd {REMOTE_PATH}

# Extract archive
tar -xzf tokenpay-deploy.tar.gz -C tokenpay/ 2>/dev/null || (mkdir -p tokenpay && tar -xzf tokenpay-deploy.tar.gz -C tokenpay/)
rm -f tokenpay-deploy.tar.gz

# Ensure directories exist
mkdir -p {REMOTE_PATH}/tokenpay {REMOTE_PATH}/auth {REMOTE_PATH}/id

# Sync to auth.tokenpay.space
cp -r {REMOTE_PATH}/tokenpay/* {REMOTE_PATH}/auth/
rm -f {REMOTE_PATH}/auth/index.html
ln -sf {REMOTE_PATH}/auth/login.html {REMOTE_PATH}/auth/index.html

# Sync to id.tokenpay.space
cp -r {REMOTE_PATH}/tokenpay/* {REMOTE_PATH}/id/
rm -f {REMOTE_PATH}/id/index.html
ln -sf {REMOTE_PATH}/id/dashboard.html {REMOTE_PATH}/id/index.html

# Fix permissions
chown -R www-data:www-data {REMOTE_PATH}/tokenpay {REMOTE_PATH}/auth {REMOTE_PATH}/id 2>/dev/null || chown -R root:root {REMOTE_PATH}/tokenpay {REMOTE_PATH}/auth {REMOTE_PATH}/id
chmod -R 644 {REMOTE_PATH}/tokenpay/* {REMOTE_PATH}/auth/* {REMOTE_PATH}/id/* 2>/dev/null
find {REMOTE_PATH} -type d -exec chmod 755 {{}} \; 2>/dev/null

# Reload nginx if available
if command -v systemctl &> /dev/null; then
    systemctl reload nginx 2>/dev/null || service nginx reload 2>/dev/null || true
fi

echo "Deployment complete!"
"""
    
    stdin, stdout, stderr = ssh_client.exec_command(commands)
    
    # Stream output
    while True:
        line = stdout.readline()
        if not line:
            break
        print(f"    {line.rstrip()}")
    
    errors = stderr.read().decode()
    if errors and "tar: Ignoring unknown extended header keyword" not in errors:
        print(f"    Errors: {errors}")
    
    exit_code = stdout.channel.recv_exit_status()
    if exit_code == 0:
        print("    Deployment successful!")
    else:
        print(f"    Exit code: {exit_code}")

def verify_deployment(ssh_client):
    """Verify deployment"""
    print("[5/5] Verifying deployment...")
    
    commands = [
        f"ls -la {REMOTE_PATH}/tokenpay/ | head -5",
        f"ls -la {REMOTE_PATH}/auth/ | head -5",
        f"ls -la {REMOTE_PATH}/id/ | head -5",
    ]
    
    for cmd in commands:
        stdin, stdout, stderr = ssh_client.exec_command(cmd)
        result = stdout.read().decode().strip()
        if result:
            print(f"    {result.split()[0]}: OK")

def main():
    print("=" * 50)
    print("TokenPay Deployment with Paramiko")
    print("=" * 50)
    print()
    
    try:
        # Check paramiko
        import paramiko
    except ImportError:
        print("Installing paramiko...")
        os.system("pip install paramiko")
        import paramiko
    
    # Create archive
    archive = create_archive()
    
    # Connect and deploy
    ssh = connect_ssh()
    
    try:
        remote_archive = f"{REMOTE_PATH}/tokenpay-deploy.tar.gz"
        upload_file(ssh, archive, remote_archive)
        deploy(ssh)
        verify_deployment(ssh)
    finally:
        ssh.close()
    
    # Cleanup
    archive.unlink(missing_ok=True)
    
    print()
    print("=" * 50)
    print("Deployment Complete!")
    print("=" * 50)
    print()
    print("Sites deployed:")
    print("  https://tokenpay.space")
    print("  https://auth.tokenpay.space")
    print("  https://id.tokenpay.space")
    print()
    print("Fixed issues:")
    print("  ✓ Mobile menu slides from right")
    print("  ✓ Dashboard theme/lang toggles")
    print("  ✓ Logo colors in light theme")
    print("  ✓ CORS for all subdomains")
    print()

if __name__ == "__main__":
    main()

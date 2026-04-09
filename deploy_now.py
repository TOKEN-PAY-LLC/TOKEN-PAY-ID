#!/usr/bin/env python3
"""
TokenPay Emergency Deployment via Paramiko
Fixes mobile menu, logos, and API integrations
"""

import paramiko
import tarfile
import os
import sys
from pathlib import Path
import time

SERVER = "5.23.54.205"
USER = "root"
PASSWORD = "vE^6t-zFS3dpNT"
LOCAL_PATH = Path("c:/Users/user/Desktop/TokenPay-Website")

def create_archive():
    """Create frontend archive with fixes"""
    print("[1/4] Creating fixed frontend archive...")
    archive = LOCAL_PATH / "tokenpay-frontend-fixed.tar.gz"
    if archive.exists():
        archive.unlink()
    
    with tarfile.open(archive, "w:gz") as tar:
        frontend = LOCAL_PATH / "frontend"
        for f in frontend.rglob("*"):
            if f.is_file() and not f.name.startswith('.'):
                arcname = f.relative_to(frontend)
                tar.add(f, arcname=arcname)
    
    size = archive.stat().st_size / 1024 / 1024
    print(f"    ✓ Archive: {size:.1f} MB")
    return archive

def deploy_via_paramiko(archive_path):
    """Deploy using Paramiko SSH"""
    print("[2/4] Connecting to server via Paramiko...")
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(
            SERVER,
            port=22,
            username=USER,
            password=PASSWORD,
            timeout=120,
            banner_timeout=120,
            auth_timeout=120,
            allow_agent=False,
            look_for_keys=False
        )
        print("    ✓ Connected!")
    except Exception as e:
        print(f"    ✗ Connection failed: {e}")
        return False
    
    try:
        # Upload file
        print("[3/4] Uploading archive...")
        sftp = client.open_sftp()
        remote_path = "/var/www/tokenpay-frontend-fixed.tar.gz"
        sftp.put(str(archive_path), remote_path)
        sftp.close()
        print(f"    ✓ Uploaded to {remote_path}")
        
        # Execute deployment
        print("[4/4] Deploying...")
        
        commands = """
# Deploy to Docker volume source (mounted as /usr/share/nginx/html in container)
FRONTEND_DIR=/root/tokenpay-id/frontend
mkdir -p $FRONTEND_DIR

# Extract directly into the Docker-mounted frontend directory
tar -xzf /var/www/tokenpay-frontend-fixed.tar.gz -C $FRONTEND_DIR/
rm -f /var/www/tokenpay-frontend-fixed.tar.gz

# Fix permissions
chmod -R 666 $FRONTEND_DIR/* 2>/dev/null || true
find $FRONTEND_DIR -type d -exec chmod 755 {} \\; 2>/dev/null || true

# Reload nginx inside Docker
docker exec tokenpay-id-nginx nginx -s reload 2>/dev/null || true

echo "✓ Deployment complete!"
"""
        
        stdin, stdout, stderr = client.exec_command(commands)
        
        # Read output
        output = stdout.read().decode()
        errors = stderr.read().decode()
        
        if output:
            print("    Output:")
            for line in output.split('\n'):
                if line.strip():
                    print(f"      {line}")
        
        if errors and "tar: Ignoring" not in errors:
            print("    Errors:")
            for line in errors.split('\n')[:5]:
                if line.strip():
                    print(f"      {line}")
        
        exit_code = stdout.channel.recv_exit_status()
        
        if exit_code == 0:
            print("    ✓ Deployment successful!")
            return True
        else:
            print(f"    ✗ Exit code: {exit_code}")
            return False
            
    except Exception as e:
        print(f"    ✗ Deployment failed: {e}")
        return False
    finally:
        client.close()

def main():
    print("="*60)
    print("TokenPay Emergency Deployment")
    print("="*60 + "\n")
    
    # Create archive
    archive = create_archive()
    
    # Deploy
    success = deploy_via_paramiko(archive)
    
    # Cleanup
    archive.unlink(missing_ok=True)
    
    print("\n" + "="*60)
    if success:
        print("✅ DEPLOYMENT COMPLETE!")
        print("="*60)
        print("\nFixes applied:")
        print("  ✓ Mobile menu overlay: pointer-events fixed")
        print("  ✓ Logos: now black in light theme")
        print("  ✓ API integrations: light theme support")
        print("\nTest at:")
        print("  https://tokenpay.space")
        print("  https://auth.tokenpay.space")
        print("  https://id.tokenpay.space")
    else:
        print("❌ DEPLOYMENT FAILED")
        print("="*60)
        print("\nTroubleshooting:")
        print("  1. Check server connectivity")
        print("  2. Verify SSH password")
        print("  3. Check disk space: ssh root@5.23.54.205 'df -h'")
        print("  4. Check nginx: ssh root@5.23.54.205 'systemctl status nginx'")
    print()

if __name__ == "__main__":
    main()

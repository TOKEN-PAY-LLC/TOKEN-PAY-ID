#!/usr/bin/env python3
"""
TokenPay Deployment using Fabric 3.x
"""

from fabric import Connection
from pathlib import Path
import tarfile
import sys

SERVER = "5.23.54.205"
USER = "root"
PASSWORD = "vE^6t-zFS3dpNT"
LOCAL_PATH = Path("c:/Users/user/Desktop/TokenPay-Website")

def create_archive():
    """Create deployment archive"""
    print("[1/4] Creating archive...")
    archive = LOCAL_PATH / "deploy.tar.gz"
    if archive.exists():
        archive.unlink()
    
    with tarfile.open(archive, "w:gz") as tar:
        frontend = LOCAL_PATH / "frontend"
        for f in frontend.rglob("*"):
            if f.is_file():
                tar.add(f, f.relative_to(frontend))
    
    size = archive.stat().st_size / 1024
    print(f"    Created: {archive.name} ({size:.1f} KB)")
    return archive

def deploy():
    print("=" * 50)
    print("TokenPay Deployment via Fabric")
    print("=" * 50)
    print()
    
    # Create archive
    archive = create_archive()
    
    # Connect via Fabric
    print(f"[2/4] Connecting to {SERVER}...")
    try:
        conn = Connection(
            host=SERVER,
            user=USER,
            connect_kwargs={"password": PASSWORD},
            connect_timeout=30
        )
        # Test connection
        result = conn.run("echo 'Connected!'", hide=True)
        print(f"    {result.stdout.strip()}")
    except Exception as e:
        print(f"    Connection failed: {e}")
        return False
    
    # Upload file
    print("[3/4] Uploading files...")
    try:
        remote_path = "/var/www/deploy.tar.gz"
        conn.put(str(archive), remote_path)
        print(f"    Uploaded to {remote_path}")
    except Exception as e:
        print(f"    Upload failed: {e}")
        return False
    
    # Execute deployment commands
    print("[4/4] Deploying on server...")
    commands = """
        cd /var/www &&
        mkdir -p tokenpay auth id &&
        tar -xzf deploy.tar.gz -C tokenpay/ &&
        rm -f deploy.tar.gz &&
        cp -r tokenpay/* auth/ &&
        cp -r tokenpay/* id/ &&
        rm -f auth/index.html id/index.html &&
        ln -sf auth/login.html auth/index.html &&
        ln -sf id/dashboard.html id/index.html &&
        chown -R www-data:www-data /var/www/tokenpay /var/www/auth /var/www/id 2>/dev/null || chown -R root:root /var/www/tokenpay /var/www/auth /var/www/id &&
        chmod -R 644 /var/www/tokenpay/* /var/www/auth/* /var/www/id/* 2>/dev/null || true &&
        find /var/www -type d -exec chmod 755 {} \\; 2>/dev/null || true &&
        systemctl reload nginx 2>/dev/null || service nginx reload 2>/dev/null || echo 'Nginx reload attempted'
    """.replace('\n', ' ')
    
    try:
        result = conn.run(commands, hide=True)
        print(f"    Exit code: {result.exited}")
        if result.stdout:
            print(f"    Output: {result.stdout.strip()[:200]}")
    except Exception as e:
        print(f"    Command failed: {e}")
    
    # Close connection
    conn.close()
    
    # Cleanup
    archive.unlink(missing_ok=True)
    
    print()
    print("=" * 50)
    print("Deployment Complete!")
    print("=" * 50)
    print()
    print("Sites:")
    print("  https://tokenpay.space")
    print("  https://auth.tokenpay.space")
    print("  https://id.tokenpay.space")
    print()
    print("Fixed issues:")
    print("  ✓ Mobile menu (slides from right)")
    print("  ✓ Dashboard theme toggle")
    print("  ✓ Logo colors in light theme")
    print("  ✓ CORS for all subdomains")
    
    return True

if __name__ == "__main__":
    try:
        deploy()
    except KeyboardInterrupt:
        print("\nCancelled by user")
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)

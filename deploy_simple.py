#!/usr/bin/env python3
"""
Simple SSH deployment using subprocess with password piping
"""

import subprocess
import sys
import tarfile
from pathlib import Path
import time

SERVER = "5.23.54.205"
USER = "root"
PASSWORD = "vE^6t-zFS3dpNT"
LOCAL_PATH = Path("c:/Users/user/Desktop/TokenPay-Website")

def run_with_password(cmd, password_input):
    """Run command and send password to stdin"""
    print(f"Running: {' '.join(cmd[:3])}...")
    
    # Start process
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    
    # Read output and send password when prompted
    output_lines = []
    password_sent = False
    
    while True:
        try:
            # Try to read line with timeout
            import select
            import os
            
            if sys.platform == 'win32':
                # Windows doesn't support select on pipes easily
                # Just send password after a delay
                if not password_sent:
                    time.sleep(2)
                    proc.stdin.write(password_input + '\n')
                    proc.stdin.flush()
                    password_sent = True
                    print("    Password sent")
                    time.sleep(10)  # Wait for transfer
                    proc.stdin.close()
                    break
            else:
                # Unix-like with select support
                import select
                ready, _, _ = select.select([proc.stdout], [], [], 1.0)
                if ready:
                    line = proc.stdout.readline()
                    if not line:
                        break
                    output_lines.append(line)
                    print(f"    {line.rstrip()}")
                    
                    if 'password:' in line.lower() and not password_sent:
                        proc.stdin.write(password_input + '\n')
                        proc.stdin.flush()
                        password_sent = True
                        print("    Password sent")
        except:
            break
    
    # Get remaining output
    stdout, stderr = proc.communicate(timeout=60)
    
    if stdout:
        print(stdout)
    if stderr:
        print(f"Stderr: {stderr}")
    
    return proc.returncode

def deploy():
    print("=" * 50)
    print("TokenPay Deployment")
    print("=" * 50)
    print()
    
    # Create archive
    print("[1/3] Creating archive...")
    archive = LOCAL_PATH / "deploy.tar.gz"
    if archive.exists():
        archive.unlink()
    
    with tarfile.open(archive, "w:gz") as tar:
        frontend = LOCAL_PATH / "frontend"
        for f in frontend.rglob("*"):
            if f.is_file():
                tar.add(f, f.relative_to(frontend))
    
    size = archive.stat().st_size / 1024
    print(f"    Archive: {size:.1f} KB")
    
    # Upload using scp with batch mode disabled
    print()
    print("[2/3] Uploading to server...")
    print("    (You'll need to type the password when prompted)")
    print(f"    Password: {PASSWORD}")
    print()
    
    cmd = [
        "scp",
        "-o", "PubkeyAuthentication=no",
        "-o", "PreferredAuthentications=password",
        "-o", "StrictHostKeyChecking=no",
        str(archive),
        f"{USER}@{SERVER}:/var/www/"
    ]
    
    print(f"Command: {' '.join(cmd)}")
    print()
    print("Running scp (you may need to type password manually)...")
    
    result = subprocess.run(cmd, capture_output=False, text=True)
    
    if result.returncode != 0:
        print(f"SCP failed with code {result.returncode}")
        return False
    
    # SSH commands
    print()
    print("[3/3] Running deployment commands...")
    ssh_cmd = [
        "ssh",
        "-o", "PubkeyAuthentication=no",
        "-o", "PreferredAuthentications=password",
        "-o", "StrictHostKeyChecking=no",
        f"{USER}@{SERVER}",
        f"cd /var/www && tar -xzf deploy.tar.gz -C tokenpay/ && rm -f deploy.tar.gz && cp -r tokenpay/* auth/ && cp -r tokenpay/* id/ && rm -f auth/index.html id/index.html && ln -sf auth/login.html auth/index.html && ln -sf id/dashboard.html id/index.html && chown -R www-data:www-data /var/www/tokenpay /var/www/auth /var/www/id && chmod -R 644 /var/www/tokenpay/* /var/www/auth/* /var/www/id/* && systemctl reload nginx || service nginx reload || echo 'Done'"
    ]
    
    print(f"Command: {' '.join(ssh_cmd[:5])}...")
    print()
    print("Running ssh commands (you may need to type password)...")
    
    result = subprocess.run(ssh_cmd, capture_output=False, text=True)
    
    # Cleanup
    archive.unlink(missing_ok=True)
    
    print()
    print("=" * 50)
    if result.returncode == 0:
        print("Deployment complete!")
    else:
        print(f"Deployment finished with code {result.returncode}")
    print("=" * 50)
    print()
    print("Sites:")
    print("  https://tokenpay.space")
    print("  https://auth.tokenpay.space")
    print("  https://id.tokenpay.space")
    
    return result.returncode == 0

if __name__ == "__main__":
    deploy()
    input("\nPress Enter to exit...")

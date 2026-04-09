#!/usr/bin/env python3
"""Deploy security & DCR changes to production server."""
import paramiko
import os
import sys

SERVER_IP = "5.23.54.205"
SERVER_PASS = "vE^6t-zFS3dpNT"
SERVER_USER = "root"

BASE = os.path.dirname(os.path.abspath(__file__))

FILES_TO_UPLOAD = [
    # (local_path, remote_path)
    (os.path.join(BASE, "backend", "server.js"), "/root/tokenpay-backend/server.js"),
    (os.path.join(BASE, "frontend", "oauth-consent.html"), "/var/www/tokenpay/oauth-consent.html"),
    (os.path.join(BASE, "frontend", ".well-known", "security.txt"), "/var/www/tokenpay/.well-known/security.txt"),
]

SYNC_COMMANDS = [
    # Ensure .well-known dir exists
    "mkdir -p /var/www/tokenpay/.well-known /var/www/auth/.well-known /var/www/id/.well-known",
    # Sync consent page + security.txt to subdomains
    "cp /var/www/tokenpay/oauth-consent.html /var/www/auth/oauth-consent.html",
    "cp /var/www/tokenpay/oauth-consent.html /var/www/id/oauth-consent.html",
    "cp /var/www/tokenpay/.well-known/security.txt /var/www/auth/.well-known/security.txt",
    "cp /var/www/tokenpay/.well-known/security.txt /var/www/id/.well-known/security.txt",
    # Fix permissions
    "chown -R www-data:www-data /var/www/tokenpay /var/www/auth /var/www/id",
    # Restart backend
    "cd /root/tokenpay-backend && pm2 restart server || (cd /root/tokenpay-backend && pm2 start server.js --name server)",
    # Reload nginx
    "systemctl reload nginx",
    # Verify
    "pm2 status",
    "curl -s -o /dev/null -w '%{http_code}' https://tokenpay.space/api/v1/health || echo 'health check skipped'",
    "curl -s https://tokenpay.space/.well-known/openid-configuration | head -c 200",
]

def main():
    print(f"=== Deploying to {SERVER_IP} ===\n")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    print(f"[1] Connecting to {SERVER_USER}@{SERVER_IP}...")
    ssh.connect(SERVER_IP, username=SERVER_USER, password=SERVER_PASS, timeout=15)
    sftp = ssh.open_sftp()
    print("    Connected!\n")

    print("[2] Uploading files...")
    for local_path, remote_path in FILES_TO_UPLOAD:
        if not os.path.exists(local_path):
            print(f"    SKIP (not found): {local_path}")
            continue
        size = os.path.getsize(local_path)
        print(f"    {os.path.basename(local_path)} ({size:,} bytes) -> {remote_path}")
        # Ensure remote directory exists
        remote_dir = os.path.dirname(remote_path)
        try:
            sftp.stat(remote_dir)
        except FileNotFoundError:
            stdin, stdout, stderr = ssh.exec_command(f"mkdir -p {remote_dir}")
            stdout.read()
        sftp.put(local_path, remote_path)
    sftp.close()
    print("    Upload complete!\n")

    print("[3] Running deployment commands...")
    for cmd in SYNC_COMMANDS:
        print(f"    $ {cmd}")
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        if out:
            for line in out.split('\n'):
                print(f"      {line}")
        if err:
            for line in err.split('\n'):
                print(f"      [stderr] {line}")
    
    ssh.close()
    print("\n=== Deployment complete! ===")

if __name__ == "__main__":
    main()

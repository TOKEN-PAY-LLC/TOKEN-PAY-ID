"""Deploy updated favicon & hero logo files to production via Paramiko SFTP."""
import paramiko
import os
import sys
import getpass

SERVER = "5.23.54.205"
USER = "root"
REMOTE_DIR = "/root/tokenpay-id/frontend"
LOCAL_DIR = os.path.join(os.path.dirname(__file__), "frontend")

# Files changed in the favicon/logo update
FILES = [
    # New image assets
    "favicon.ico",
    "icon-192.png",
    "icon-512.png",
    "apple-touch-icon.png",
    "hero-logo-white.png",
    "hero-logo-black.png",
    # Updated HTML (favicon v=5 + hero section)
    "index.html",
    "admin.html",
    "dashboard.html",
    "docs.html",
    "login.html",
    "oauth-consent.html",
    "oauth-widget.html",
    "privacy.html",
    "qr-login.html",
    "register.html",
    "terms.html",
    "welcome.html",
    # Updated CSS & manifest
    "styles.css",
    "manifest.json",
]

def main():
    print(f"[*] Connecting to {SERVER}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    password = os.environ.get("DEPLOY_PASS") or getpass.getpass(f"Password for {USER}@{SERVER}: ")
    ssh.connect(SERVER, username=USER, password=password, allow_agent=False, look_for_keys=False)
    sftp = ssh.open_sftp()

    ok, fail = 0, 0
    for f in FILES:
        local = os.path.join(LOCAL_DIR, f)
        remote = f"{REMOTE_DIR}/{f}"
        if not os.path.exists(local):
            print(f"  [!] SKIP (missing locally): {f}")
            fail += 1
            continue
        size = os.path.getsize(local)
        try:
            sftp.put(local, remote)
            print(f"  [+] {f} ({size:,} bytes)")
            ok += 1
        except Exception as e:
            print(f"  [!] FAIL {f}: {e}")
            fail += 1

    print(f"\n[*] Uploaded {ok}/{len(FILES)} files ({fail} failures)")

    # Also update host process frontend if it exists
    HOST_DIR = "/var/www/frontend"
    try:
        sftp.stat(HOST_DIR)
        print(f"\n[*] Host frontend dir found at {HOST_DIR}, syncing there too...")
        for f in FILES:
            local = os.path.join(LOCAL_DIR, f)
            if os.path.exists(local):
                try:
                    sftp.put(local, f"{HOST_DIR}/{f}")
                    print(f"  [+] {HOST_DIR}/{f}")
                except:
                    pass
    except FileNotFoundError:
        pass

    # Reload nginx to clear any cached responses
    print("\n[*] Reloading nginx in Docker container...")
    stdin, stdout, stderr = ssh.exec_command("docker exec tokenpay-id-nginx nginx -s reload 2>&1")
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        print(f"  stdout: {out}")
    if err:
        print(f"  stderr: {err}")
    print("  [+] nginx reloaded")

    # Quick verification
    print("\n[*] Verifying deployment...")
    stdin, stdout, stderr = ssh.exec_command(f"ls -la {REMOTE_DIR}/favicon.ico {REMOTE_DIR}/hero-logo-white.png {REMOTE_DIR}/hero-logo-black.png {REMOTE_DIR}/icon-192.png 2>&1")
    print(stdout.read().decode().strip())

    sftp.close()
    ssh.close()
    print("\n[OK] Deploy complete!")

if __name__ == "__main__":
    main()

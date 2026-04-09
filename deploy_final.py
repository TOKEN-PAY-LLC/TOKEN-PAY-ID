#!/usr/bin/env python3
"""Deploy frontend files directly to Docker volume source on server"""
import paramiko
import tarfile
from pathlib import Path

SERVER = "5.23.54.205"
USER = "root"
PASSWORD = "vE^6t-zFS3dpNT"
LOCAL_PATH = Path("c:/Users/user/Desktop/TokenPay-Website")
REMOTE_FRONTEND = "/root/tokenpay-id/frontend"

def run_cmd(client, cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    code = stdout.channel.recv_exit_status()
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    return code, out, err

def main():
    # Create archive
    print("[1/4] Creating archive...")
    archive = LOCAL_PATH / "tokenpay-frontend-deploy.tar.gz"
    if archive.exists():
        archive.unlink()
    with tarfile.open(archive, "w:gz") as tar:
        frontend = LOCAL_PATH / "frontend"
        for f in frontend.rglob("*"):
            if f.is_file() and ".wrangler" not in str(f) and not f.name.startswith("."):
                arcname = str(f.relative_to(frontend))
                tar.add(f, arcname=arcname)
    size_mb = archive.stat().st_size / 1024 / 1024
    print(f"    Archive: {size_mb:.1f} MB")

    # Connect
    print("[2/4] Connecting...")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(SERVER, port=22, username=USER, password=PASSWORD,
              timeout=120, banner_timeout=120, auth_timeout=120,
              allow_agent=False, look_for_keys=False)
    print("    Connected!")

    # Upload
    print("[3/4] Uploading...")
    sftp = c.open_sftp()
    remote_archive = "/tmp/tp-frontend.tar.gz"
    sftp.put(str(archive), remote_archive)
    sftp.close()
    print(f"    Uploaded to {remote_archive}")

    # Deploy step by step
    print("[4/4] Deploying to Docker volume...")

    steps = [
        f"mkdir -p {REMOTE_FRONTEND}",
        f"mkdir -p {REMOTE_FRONTEND}/sdk",
        f"tar -xzf {remote_archive} -C {REMOTE_FRONTEND}/",
        f"rm -f {remote_archive}",
        f"ls -la {REMOTE_FRONTEND}/qrcode-min.js {REMOTE_FRONTEND}/theme-init.js {REMOTE_FRONTEND}/styles.css 2>&1",
        f"head -20 {REMOTE_FRONTEND}/login.html | grep theme-init",
        f"grep pageReveal {REMOTE_FRONTEND}/styles.css | head -1",
        "docker exec tokenpay-id-nginx nginx -s reload 2>&1",
    ]

    for i, cmd in enumerate(steps):
        code, out, err = run_cmd(c, cmd)
        label = cmd.split("/")[-1][:50] if "/" in cmd else cmd[:50]
        status = "OK" if code == 0 else f"ERR({code})"
        detail = out[:120] if out else (err[:120] if err else "")
        print(f"    [{status}] {label}")
        if detail:
            print(f"           {detail}")

    # Cleanup local
    archive.unlink(missing_ok=True)
    c.close()
    print("\nDone!")

if __name__ == "__main__":
    main()

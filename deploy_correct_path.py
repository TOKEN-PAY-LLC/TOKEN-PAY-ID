import paramiko, os

SERVER = "5.23.54.205"
USER = "root"
PASSWORD = "vE^6t-zFS3dpNT"
LOCAL_DIR = r"c:\Users\user\Desktop\TokenPay-Website\frontend"
REMOTE_DIR = "/root/tokenpay-id/frontend"
FILES = ["index.html", "theme-init.js", "script.js", "styles.css", "docs.html"]

print("Connecting to", SERVER)
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(SERVER, username=USER, password=PASSWORD)
sftp = ssh.open_sftp()

for f in FILES:
    local = os.path.join(LOCAL_DIR, f)
    remote = f"{REMOTE_DIR}/{f}"
    print(f"  Uploading {f} -> {remote}")
    sftp.put(local, remote)

sftp.close()
print("Files uploaded to Docker mount path.")

# Verify
cmds = [
    "docker exec tokenpay-id-nginx grep -o 'v=2026[0-9a-z]*' /usr/share/nginx/html/index.html | head -3",
    "docker exec tokenpay-id-nginx grep -c 'tpid-btn-hero' /usr/share/nginx/html/index.html",
    "docker exec tokenpay-id-nginx grep -c 'data-en' /usr/share/nginx/html/index.html",
    "docker exec tokenpay-id-nginx grep -c 'bank' /usr/share/nginx/html/index.html || echo '0'",
    "curl -s https://tokenpay.space/ 2>/dev/null | grep -o 'v=2026[0-9a-z]*' | head -1",
]
for cmd in cmds:
    print(f"\n$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    print(stdout.read().decode().strip())

ssh.close()
print("\nDONE — deployment complete!")

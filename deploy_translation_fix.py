import paramiko, os

SERVER = "5.23.54.205"
USER = "root"
PASSWORD = "vE^6t-zFS3dpNT"
LOCAL_DIR = r"c:\Users\user\Desktop\TokenPay-Website\frontend"
REMOTE_DIR = "/var/www/tokenpay"
FILES = ["index.html", "theme-init.js", "script.js", "styles.css"]

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
print("Files uploaded. Syncing subdomains...")

cmds = [
    "cp /var/www/tokenpay/index.html /var/www/tokenpay/theme-init.js /var/www/tokenpay/script.js /var/www/tokenpay/styles.css /var/www/auth/",
    "cp /var/www/tokenpay/index.html /var/www/tokenpay/theme-init.js /var/www/tokenpay/script.js /var/www/tokenpay/styles.css /var/www/id/",
    "chown -R www-data:www-data /var/www/tokenpay /var/www/auth /var/www/id",
    "systemctl reload nginx",
]
for cmd in cmds:
    print(f"  $ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out: print(f"    {out.strip()}")
    if err: print(f"    ERR: {err.strip()}")

ssh.close()
print("DONE — deployment complete!")

import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("5.23.54.205", username="root", password="vE^6t-zFS3dpNT")

# Check deployed files are correct
cmds = [
    "head -6 /var/www/tokenpay/index.html",
    "grep 'tpid-btn-hero' /var/www/tokenpay/index.html | wc -l",
    "grep 'data-en' /var/www/tokenpay/index.html | wc -l",
    "head -3 /var/www/tokenpay/theme-init.js",
    "grep '20260330a' /var/www/tokenpay/index.html | wc -l",
]
for cmd in cmds:
    print(f"$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    print(stdout.read().decode().strip())

ssh.close()
print("\nVerification complete!")

import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('5.23.54.205', username='root', password='vE^6t-zFS3dpNT')

checks = [
    ("Docker mounts", "docker inspect tokenpay-id-nginx --format='{{range .Mounts}}{{.Source}} -> {{.Destination}}\n{{end}}'"),
    ("Host file sizes", "ls -la /root/tokenpay-id/frontend/*.css /root/tokenpay-id/frontend/*.html 2>&1"),
    ("Container CSS overflow fix", "docker exec tokenpay-id-nginx grep -c 'overflow-x:hidden' /usr/share/nginx/html/styles.css 2>&1"),
    ("Container TPID light fix", "docker exec tokenpay-id-nginx grep -c 'body.light .tpid-btn{background:#111' /usr/share/nginx/html/styles.css 2>&1"),
    ("Container docs version", "docker exec tokenpay-id-nginx grep -o 'v=2026[0-9a-z]*' /usr/share/nginx/html/docs.html 2>&1 | head -2"),
    ("Nginx config", "docker exec tokenpay-id-nginx cat /etc/nginx/conf.d/default.conf 2>&1 | head -20"),
    ("Live site check", "curl -sI https://tokenpay.space/styles.css?v=20260403a 2>&1 | head -8"),
]

for name, cmd in checks:
    print(f"\n=== {name} ===")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    print(out if out else err if err else "(empty)")

ssh.close()

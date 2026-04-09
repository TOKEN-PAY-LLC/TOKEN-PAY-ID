import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("5.23.54.205", username="root", password="vE^6t-zFS3dpNT")

cmds = [
    # Find the actual document root in nginx config
    "docker exec tokenpay-id-nginx grep -n 'root ' /etc/nginx/conf.d/default.conf",
    # Check docker volume mounts
    "docker inspect tokenpay-id-nginx --format='{{range .Mounts}}{{.Source}} -> {{.Destination}}\n{{end}}'",
    # Check if files are inside the container or mounted
    "docker exec tokenpay-id-nginx ls -la /var/www/html/index.html 2>/dev/null || docker exec tokenpay-id-nginx ls -la /usr/share/nginx/html/index.html 2>/dev/null",
    # Check the version served from inside container
    "docker exec tokenpay-id-nginx grep -o 'v=2026[0-9a-z]*' /var/www/html/index.html 2>/dev/null || docker exec tokenpay-id-nginx grep -o 'v=2026[0-9a-z]*' /usr/share/nginx/html/index.html 2>/dev/null",
    # docker-compose file location
    "find / -name 'docker-compose.yml' -path '*/tokenpay*' 2>/dev/null | head -5",
    "cat /root/docker-compose.yml 2>/dev/null | head -40 || cat /opt/tokenpay/docker-compose.yml 2>/dev/null | head -40",
]

for cmd in cmds:
    print(f"\n$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out: print(out)
    if err: print(f"ERR: {err}")

ssh.close()

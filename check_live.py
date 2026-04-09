import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("5.23.54.205", username="root", password="vE^6t-zFS3dpNT")

cmds = [
    # Full headers from live site
    "curl -sI https://tokenpay.space/ 2>/dev/null",
    # Check if live site serves the NEW version
    "curl -s https://tokenpay.space/ 2>/dev/null | grep -o 'v=2026[0-9a-z]*'",
    # Check if live site has tpid-btn-hero
    "curl -s https://tokenpay.space/ 2>/dev/null | grep -c 'tpid-btn-hero'",
    # Check if live site has data-en on section-tag
    "curl -s https://tokenpay.space/ 2>/dev/null | grep -c 'data-en'",
    # Check if Cloudflare Workers is deployed
    "which wrangler 2>/dev/null || npm list -g wrangler 2>/dev/null || echo 'wrangler not found'",
    # Check docker nginx is serving from /var/www/tokenpay
    "docker exec tokenpay-id-nginx cat /etc/nginx/conf.d/default.conf 2>/dev/null | head -30 || docker exec tokenpay-id-nginx cat /etc/nginx/nginx.conf 2>/dev/null | head -50",
]

for cmd in cmds:
    print(f"\n$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out: print(out)
    if err and 'wrangler' not in cmd: print(f"ERR: {err}")

ssh.close()

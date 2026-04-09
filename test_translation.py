import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("5.23.54.205", username="root", password="vE^6t-zFS3dpNT")

cmds = [
    # Check for JS syntax errors
    "node -e \"$(cat /var/www/tokenpay/script.js)\" 2>&1 | head -20 || echo 'JS syntax check done'",
    # Check if the lang toggle button exists and is properly connected
    "grep -c 'langToggle' /var/www/tokenpay/index.html",
    "grep -c 'lang-label' /var/www/tokenpay/index.html",
    # Check if data-en attributes are actually in the deployed HTML
    "grep -m5 'data-en=' /var/www/tokenpay/index.html",
    # Check Cloudflare caching headers
    "curl -sI https://tokenpay.space/index.html 2>/dev/null | grep -i 'cache\\|cf-\\|age'",
    "curl -sI https://tokenpay.space/script.js?v=20260330a 2>/dev/null | grep -i 'cache\\|cf-\\|age'",
    # Check if there are any script errors in the HTML inline script
    "sed -n '30,51p' /var/www/tokenpay/index.html",
    # CRITICAL: Check if the right-click prevention blocks other events
    "grep -n 'contextmenu\\|preventDefault' /var/www/tokenpay/script.js",
]

for cmd in cmds:
    print(f"\n$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out: print(out)
    if err: print(f"ERR: {err}")

ssh.close()

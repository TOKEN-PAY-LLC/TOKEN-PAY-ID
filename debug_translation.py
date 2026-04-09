import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("5.23.54.205", username="root", password="vE^6t-zFS3dpNT")

cmds = [
    # Check theme-init.js content
    "echo '=== theme-init.js ===' && cat /var/www/tokenpay/theme-init.js",
    # Check script.js LanguageManager section
    "echo '=== LanguageManager in script.js ===' && sed -n '/class LanguageManager/,/^}/p' /var/www/tokenpay/script.js",
    # Check if hero has tpid-btn-hero
    "echo '=== Hero buttons ===' && grep -n 'tpid-btn-hero\\|hero-buttons' /var/www/tokenpay/index.html",
    # Check data-en count
    "echo '=== data-en count ===' && grep -c 'data-en' /var/www/tokenpay/index.html",
    # Check lang toggle button
    "echo '=== lang toggle ===' && grep -n 'langToggle' /var/www/tokenpay/index.html",
    # Check version strings
    "echo '=== versions ===' && grep -n '20260330' /var/www/tokenpay/index.html",
]

for cmd in cmds:
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    print(out)
    if err:
        print(f"ERR: {err}")

ssh.close()

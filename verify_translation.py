import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("5.23.54.205", username="root", password="vE^6t-zFS3dpNT")

cmds = [
    # Verify key elements have all 3 language data attributes
    "echo '=== Sample elements with all 3 langs ===' && curl -s https://tokenpay.space/ 2>/dev/null | grep -oP 'data-ru=\"[^\"]+\" data-en=\"[^\"]+\" data-zh=\"[^\"]+\"' | head -10",
    # Verify the hero TPID button
    "echo '=== Hero TPID button ===' && curl -s https://tokenpay.space/ 2>/dev/null | grep 'tpid-btn-hero'",
    # Verify theme-init.js has auto-detect
    "echo '=== theme-init.js navigator.language ===' && curl -s 'https://tokenpay.space/theme-init.js?v=20260330a' 2>/dev/null | grep -c 'navigator.language'",
    # Verify script.js has LanguageManager with title update
    "echo '=== script.js title update ===' && curl -s 'https://tokenpay.space/script.js?v=20260330a' 2>/dev/null | grep -c 'TOKEN PAY LLC'",
    # Verify script.js has no autoDetect API call
    "echo '=== No autoDetect API ===' && curl -s 'https://tokenpay.space/script.js?v=20260330a' 2>/dev/null | grep -c 'autoDetect'",
]

for cmd in cmds:
    stdin, stdout, stderr = ssh.exec_command(cmd)
    print(stdout.read().decode().strip())
    print()

ssh.close()

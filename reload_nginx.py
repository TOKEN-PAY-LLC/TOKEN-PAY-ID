import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('5.23.54.205', username='root', password='vE^6t-zFS3dpNT', timeout=15)

cmds = [
    'docker ps --format "{{.Names}} {{.Image}}"',
    'systemctl is-active nginx',
    'nginx -s reload 2>&1 || systemctl reload nginx 2>&1',
    'curl -sk https://tokenpay.space/ | grep -o "styles.css?v=[^\\"]*" | head -1',
]
for cmd in cmds:
    print(f'> {cmd}')
    _, so, se = ssh.exec_command(cmd)
    print(so.read().decode().strip() or se.read().decode().strip() or '(empty)')
    print()

ssh.close()

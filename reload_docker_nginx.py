import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('5.23.54.205', username='root', password='vE^6t-zFS3dpNT', timeout=15)

cmds = [
    # Check where nginx serves files from inside docker
    'docker exec tokenpay-id-nginx ls /usr/share/nginx/html/ 2>/dev/null | head -20',
    'docker exec tokenpay-id-nginx cat /etc/nginx/conf.d/default.conf 2>/dev/null | grep -i root | head -5',
    # Check if docker volume mounts the frontend
    'docker inspect tokenpay-id-nginx --format "{{range .Mounts}}{{.Source}} -> {{.Destination}}\n{{end}}"',
    # Reload nginx inside docker
    'docker exec tokenpay-id-nginx nginx -s reload 2>&1',
    # Verify
    'curl -sk https://tokenpay.space/ | grep -o "styles.css?v=[^\\"]*" | head -1',
    'curl -sk https://tokenpay.space/ | grep -o "Условия использования" | head -1',
]
for cmd in cmds:
    print(f'> {cmd}')
    _, so, se = ssh.exec_command(cmd)
    print(so.read().decode().strip() or se.read().decode().strip() or '(empty)')
    print()

ssh.close()

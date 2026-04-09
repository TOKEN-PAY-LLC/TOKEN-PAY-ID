import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('5.23.54.205', username='root', password='vE^6t-zFS3dpNT')
stdin, stdout, stderr = ssh.exec_command('docker ps --format "{{.Names}}  {{.Image}}  {{.Status}}"')
print(stdout.read().decode())
ssh.close()

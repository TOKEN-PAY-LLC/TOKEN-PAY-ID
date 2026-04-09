import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("5.23.54.205", username="root", password="vE^6t-zFS3dpNT")

# Find nginx container and reload
cmds = [
    "docker ps --format '{{.Names}}' | grep -i nginx",
    "docker exec tokenpay-nginx nginx -s reload 2>&1 || docker exec $(docker ps --format '{{.Names}}' | grep -i nginx | head -1) nginx -s reload 2>&1 || echo 'No nginx container found'",
]
for cmd in cmds:
    print(f"$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    print(stdout.read().decode().strip())
    err = stderr.read().decode().strip()
    if err:
        print(f"  ERR: {err}")

ssh.close()
print("Done")

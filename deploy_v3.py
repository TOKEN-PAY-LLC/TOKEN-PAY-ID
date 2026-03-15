import paramiko
import os, time

HOST = '5.23.54.205'
USER = 'root'
PASSWD = 'vE^6t-zFS3dpNT'
REMOTE_DIR = '/root/tokenpay-id'
LOCAL_TAR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'deploy.tar.gz')

def get_ssh():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWD, timeout=15)
    return ssh

def run(ssh, cmd, timeout=120):
    print(f'[CMD] {cmd[:120]}')
    try:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode()
        err = stderr.read().decode()
        code = stdout.channel.recv_exit_status()
        if out.strip(): print(out.strip()[:600])
        if err.strip(): print(f'[STDERR] {err.strip()[:400]}')
        return code
    except Exception as e:
        print(f'[ERR] {e}')
        return -1

# Step 1: Upload
ssh = get_ssh()
print('[OK] Connected')
sftp = ssh.open_sftp()
run(ssh, f'mkdir -p {REMOTE_DIR}')
print(f'[UPLOAD] deploy.tar.gz')
sftp.put(LOCAL_TAR, f'{REMOTE_DIR}/deploy.tar.gz')
sftp.close()
print('[OK] Uploaded')
run(ssh, f'cd {REMOTE_DIR} && tar -xzf deploy.tar.gz')
ssh.close()

# Step 2: Rebuild (new connection for long operation)
ssh = get_ssh()
run(ssh, f'docker rm -f tokenpay-id-api tokenpay-id-nginx 2>/dev/null || true')
run(ssh, f'cd {REMOTE_DIR} && docker compose up -d --build 2>&1', timeout=300)
ssh.close()

# Step 3: Verify (new connection)
time.sleep(6)
ssh = get_ssh()
run(ssh, 'docker ps --format "table {{.Names}}\\t{{.Status}}\\t{{.Ports}}"')
run(ssh, 'docker exec tokenpay-id-api wget -qO- http://localhost:8080/health 2>&1')
run(ssh, 'curl -sk https://localhost/ 2>&1 | head -3')
ssh.close()
print('\n=== DEPLOY DONE ===')

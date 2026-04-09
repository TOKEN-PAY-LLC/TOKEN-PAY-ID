import paramiko, os, json

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('5.23.54.205', username='root', password='vE^6t-zFS3dpNT', timeout=15)

def run(cmd):
    _, o, e = ssh.exec_command(cmd)
    out = o.read().decode().strip()
    err = e.read().decode().strip()
    if out: print("OUT:", out)
    if err and 'warning' not in err.lower(): print("ERR:", err)
    return out, err

sftp = ssh.open_sftp()

# 1. Deploy email-service.js to API container
print("=== Deploying email-service.js ===")
local_email = r'C:\Users\user\Desktop\TokenPay-Website\backend\email-service.js'
sftp.put(local_email, '/tmp/email-service.js')

# Find where email-service.js lives in the api container
out, _ = run("docker exec tokenpay-id-api find /app -name 'email-service.js' 2>/dev/null")
print("email-service.js location:", out)
api_email_path = out.strip().split('\n')[0] if out else '/app/email-service.js'
run(f"docker cp /tmp/email-service.js tokenpay-id-api:{api_email_path}")
print(f"  -> deployed to {api_email_path}")

# Reload the API container (graceful — just restart the process)
run("docker restart tokenpay-id-api")
print("  -> tokenpay-id-api restarted")

# 2. Deploy frontend HTML files
print("\n=== Deploying frontend HTML files ===")
FRONTEND = r'C:\Users\user\Desktop\TokenPay-Website\frontend'
out2, _ = run("docker inspect tokenpay-id-nginx --format '{{json .Mounts}}'")
mounts = json.loads(out2) if out2 else []
html_src = next((m['Source'] for m in mounts if 'html' in m.get('Destination', '')), None)
print("HTML src:", html_src)

for fname in ['oauth-consent.html', 'dashboard.html']:
    local = os.path.join(FRONTEND, fname)
    sftp.put(local, f'{html_src}/{fname}')
    print(f"  -> {fname}")

sftp.close()

# Verify
import time; time.sleep(5)
run("docker ps --filter name=tokenpay-id-api --format '{{.Status}}'")

ssh.close()
print("Deploy complete.")

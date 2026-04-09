"""Diagnose email delivery issues and check QR login UX in dashboard"""
import paramiko

HOST = '5.23.54.205'
USER = 'root'
PASS = 'vE^6t-zFS3dpNT'

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=15)

    print('=== 1. BACKEND LOGS (last 50 lines, email related) ===')
    stdin, stdout, stderr = ssh.exec_command('docker logs tokenpay-id-api --tail 100 2>&1 | grep -i "email\\|smtp\\|mail\\|error\\|fail\\|reject\\|timeout" | tail -50')
    print(stdout.read().decode())

    print('=== 2. SMTP CONFIG in server.js ===')
    stdin, stdout, stderr = ssh.exec_command("grep -n 'smtp\\|SMTP\\|nodemailer\\|createTransport\\|MAIL_\\|EMAIL_' /root/tokenpay-id/backend/server.js | head -30")
    print(stdout.read().decode())

    print('=== 3. ENV / DOCKER ENV (email vars) ===')
    stdin, stdout, stderr = ssh.exec_command("docker exec tokenpay-id-api env 2>/dev/null | grep -i 'smtp\\|mail\\|email' | head -20")
    print(stdout.read().decode())

    print('=== 4. .env file (email config) ===')
    stdin, stdout, stderr = ssh.exec_command("cat /root/tokenpay-id/.env 2>/dev/null | grep -i 'smtp\\|mail\\|email' | head -20")
    env_out = stdout.read().decode()
    if not env_out.strip():
        stdin, stdout, stderr = ssh.exec_command("cat /root/tokenpay-id/backend/.env 2>/dev/null | grep -i 'smtp\\|mail\\|email' | head -20")
        env_out = stdout.read().decode()
    print(env_out or '(no .env found)')

    print('=== 5. FULL BACKEND LOGS (last 30 lines) ===')
    stdin, stdout, stderr = ssh.exec_command('docker logs tokenpay-id-api --tail 30 2>&1')
    print(stdout.read().decode())

    print('=== 6. Test SMTP connection ===')
    stdin, stdout, stderr = ssh.exec_command("docker exec tokenpay-id-api node -e \"const n=require('nodemailer');const t=n.createTransport({host:'smtp.timeweb.ru',port:465,secure:true,auth:{user:process.env.SMTP_USER||'info@tokenpay.space',pass:process.env.SMTP_PASS||''}});t.verify().then(()=>console.log('SMTP OK')).catch(e=>console.log('SMTP FAIL:',e.message))\" 2>&1", timeout=15)
    print(stdout.read().decode())

    print('=== 7. QR code in dashboard ===')
    stdin, stdout, stderr = ssh.exec_command("grep -n 'qr\\|QR\\|scan\\|сканир' /root/tokenpay-id/frontend/dashboard.html | head -30")
    print(stdout.read().decode())

    ssh.close()

if __name__ == '__main__':
    main()

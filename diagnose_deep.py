"""Deep diagnosis: email delivery + QR login flow"""
import paramiko

HOST = '5.23.54.205'
USER = 'root'
PASS = 'vE^6t-zFS3dpNT'

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=15)

    # 1. Check if there are EMAIL errors in recent logs (not just [EMAIL] Sent)
    print('=== 1. ALL recent backend logs (last 80 lines) ===')
    stdin, stdout, stderr = ssh.exec_command('docker logs tokenpay-id-api --tail 80 2>&1')
    print(stdout.read().decode())

    # 2. Try to trigger a real email send and see what happens
    print('=== 2. Test email send via API ===')
    stdin, stdout, stderr = ssh.exec_command(
        """curl -sk -X POST https://tokenpay.space/api/v1/auth/send-code -H 'Content-Type: application/json' -d '{"email":"info@tokenpay.space","type":"login"}' 2>&1"""
    )
    print('Response:', stdout.read().decode())

    # 3. Check logs right after the send
    print('=== 3. Logs after test send ===')
    import time; time.sleep(3)
    stdin, stdout, stderr = ssh.exec_command('docker logs tokenpay-id-api --tail 10 2>&1')
    print(stdout.read().decode())

    # 4. Check sendEmail function in server.js
    print('=== 4. sendEmail function ===')
    stdin, stdout, stderr = ssh.exec_command("grep -n -A20 'function sendEmail\\|const sendEmail\\|async.*sendEmail' /root/tokenpay-id/backend/server.js | head -40")
    print(stdout.read().decode())

    # 5. Check nginx routes for /qr-login
    print('=== 5. Nginx config for /qr-login route ===')
    stdin, stdout, stderr = ssh.exec_command("grep -rn 'qr-login\\|qr_login\\|/qr' /etc/nginx/ 2>/dev/null; docker exec tokenpay-id-nginx grep -rn 'qr-login\\|qr_login\\|/qr' /etc/nginx/ 2>/dev/null")
    print(stdout.read().decode() or '(none found)')

    # 6. Check if /qr-login page exists
    print('=== 6. Check /qr-login page ===')
    stdin, stdout, stderr = ssh.exec_command("ls -la /root/tokenpay-id/frontend/qr-login* 2>/dev/null; curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/qr-login")
    print(stdout.read().decode())

    # 7. Dashboard QR poll function
    print('=== 7. Dashboard QR poll code ===')
    stdin, stdout, stderr = ssh.exec_command("grep -n -A20 'function startQRPoll\\|function generateQR' /root/tokenpay-id/frontend/dashboard.html | head -60")
    print(stdout.read().decode())

    # 8. Check QR confirm endpoint flow
    print('=== 8. QR login-confirm endpoint ===')
    stdin, stdout, stderr = ssh.exec_command("grep -n -A15 'login-confirm' /root/tokenpay-id/backend/server.js | head -30")
    print(stdout.read().decode())

    ssh.close()

if __name__ == '__main__':
    main()

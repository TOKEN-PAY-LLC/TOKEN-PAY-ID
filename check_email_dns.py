"""Check email DNS records and test delivery"""
import paramiko, time

HOST = '5.23.54.205'
USER = 'root'
PASS = 'vE^6t-zFS3dpNT'

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=15)

    print('=== 1. SPF record ===')
    stdin, stdout, stderr = ssh.exec_command('dig +short TXT tokenpay.space | grep spf')
    out = stdout.read().decode().strip()
    print(out or '(no SPF record!)')

    print('\n=== 2. DKIM record ===')
    stdin, stdout, stderr = ssh.exec_command('dig +short TXT default._domainkey.tokenpay.space')
    out = stdout.read().decode().strip()
    print(out or '(no DKIM record)')

    print('\n=== 3. DMARC record ===')
    stdin, stdout, stderr = ssh.exec_command('dig +short TXT _dmarc.tokenpay.space')
    out = stdout.read().decode().strip()
    print(out or '(no DMARC record!)')

    print('\n=== 4. MX records ===')
    stdin, stdout, stderr = ssh.exec_command('dig +short MX tokenpay.space')
    print(stdout.read().decode().strip() or '(no MX records!)')

    print('\n=== 5. SMTP password check (is SMTP_PASS set?) ===')
    stdin, stdout, stderr = ssh.exec_command("docker exec tokenpay-id-api node -e \"console.log('SMTP_PASS length:', (process.env.SMTP_PASS||'').length)\" 2>&1")
    print(stdout.read().decode().strip())

    print('\n=== 6. Test real email send + detailed SMTP log ===')
    stdin, stdout, stderr = ssh.exec_command("""docker exec tokenpay-id-api node -e "
const n=require('nodemailer');
const t=n.createTransport({
    host:'smtp.timeweb.ru',port:465,secure:true,
    auth:{user:process.env.SMTP_USER||'info@tokenpay.space',pass:process.env.SMTP_PASS||''},
    logger:true,debug:true
});
t.sendMail({
    from:'\"TOKEN PAY ID\" <info@tokenpay.space>',
    to:'info@tokenpay.space',
    subject:'Test delivery ' + Date.now(),
    text:'Email delivery test'
}).then(i=>console.log('OK:', JSON.stringify(i))).catch(e=>console.log('FAIL:', e.message));
" 2>&1""", timeout=20)
    print(stdout.read().decode())

    print('\n=== 7. Recent errors in backend log ===')
    stdin, stdout, stderr = ssh.exec_command('docker logs tokenpay-id-api --since 5m 2>&1 | grep -i "error\\|fail\\|reject\\|bounce"')
    out = stdout.read().decode().strip()
    print(out or '(no errors in last 5 minutes)')

    ssh.close()

if __name__ == '__main__':
    main()

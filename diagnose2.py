import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('5.23.54.205', username='root', password='vE^6t-zFS3dpNT', timeout=15)

cmds = [
    # Email deliverability deep check
    ("dig +short TXT tokenpay.space @8.8.8.8 2>/dev/null", "SPF record (Google DNS)"),
    ("dig +short TXT _dmarc.tokenpay.space @8.8.8.8 2>/dev/null", "DMARC record"),
    ("dig +short TXT default._domainkey.tokenpay.space @8.8.8.8 2>/dev/null", "DKIM record"),
    ("dig +short TXT mail._domainkey.tokenpay.space @8.8.8.8 2>/dev/null", "DKIM (mail) record"),
    ("dig +short A tokenpay.space @8.8.8.8 2>/dev/null", "A record"),
    ("dig +short NS tokenpay.space @8.8.8.8 2>/dev/null", "NS records (DNS provider)"),
    # Test actual email sending with detailed SMTP log
    ("docker exec tokenpay-id-api node -e \"const es = require('./email-service.js'); es.initTransporter(); es.sendEmail('ichernykh08@gmail.com', 'Test delivery — TOKEN PAY ID', '<h1>Test</h1><p>If you see this, email delivery works.</p>').then(r => console.log('OK:', JSON.stringify(r))).catch(e => console.log('ERR:', e.message))\" 2>&1", "Test email send"),
    # Check Timeweb DKIM
    ("dig +short TXT timeweb._domainkey.tokenpay.space @8.8.8.8 2>/dev/null", "DKIM (timeweb) record"),
    # Check how many emails were sent total
    ("docker logs tokenpay-id-api 2>&1 | grep -c 'Sent to'", "Total emails sent"),
    # Check for any rejection/bounce
    ("docker logs tokenpay-id-api 2>&1 | grep -i 'reject\\|bounce\\|blacklist\\|blocked' | tail -5", "Rejections/bounces"),
]

print("=" * 60)
print("EMAIL DELIVERABILITY DEEP DIAGNOSIS")
print("=" * 60)

for cmd, label in cmds:
    print(f"\n--- {label} ---")
    _, so, se = ssh.exec_command(cmd, timeout=30)
    out = so.read().decode().strip()
    err = se.read().decode().strip()
    print(out or err or "(empty)")

ssh.close()

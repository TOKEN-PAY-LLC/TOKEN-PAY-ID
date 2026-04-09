import paramiko, time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('5.23.54.205', username='root', password='vE^6t-zFS3dpNT', timeout=15)

print("=" * 60)
print("DEEP EMAIL DIAGNOSIS")
print("=" * 60)

cmds = [
    # 1. Check DNS propagation
    ("dig +short TXT tokenpay.space @8.8.8.8 2>/dev/null", "SPF @ Google DNS"),
    ("dig +short TXT tokenpay.space @1.1.1.1 2>/dev/null", "SPF @ Cloudflare DNS"),
    ("dig +short TXT _dmarc.tokenpay.space @8.8.8.8 2>/dev/null", "DMARC @ Google DNS"),
    ("dig +short TXT _dmarc.tokenpay.space @1.1.1.1 2>/dev/null", "DMARC @ Cloudflare DNS"),
    ("for s in default mail dkim timeweb info; do r=$(dig +short TXT ${s}._domainkey.tokenpay.space @8.8.8.8 2>/dev/null); [ -n \"$r\" ] && echo \"DKIM selector: $s -> $r\"; done; echo 'DKIM scan done'", "DKIM selectors scan"),

    # 2. Check recent email logs
    ("docker logs tokenpay-id-api --since=2h 2>&1 | grep -i '\\[EMAIL\\]' | tail -30", "Email logs (last 2h)"),
    ("docker logs tokenpay-id-api --since=2h 2>&1 | grep -iE 'error|fail|reject|spam|blocked|blacklist|bounce|defer' | tail -20", "Error logs (last 2h)"),

    # 3. Test actual SMTP handshake and message delivery with verbose output
    ("""docker exec tokenpay-id-api node -e "
const nodemailer = require('nodemailer');
const transporter = nodemailer.createTransport({
  host: 'smtp.timeweb.ru', port: 465, secure: true,
  auth: { user: 'info@tokenpay.space', pass: '1cgukl9kh5' },
  debug: true, logger: true
});
transporter.sendMail({
  from: 'TOKEN PAY ID <info@tokenpay.space>',
  to: 'info@tokenpay.space',
  subject: 'Тест доставки ' + new Date().toISOString(),
  html: '<h1>Тест</h1><p>Если видите это - письмо дошло.</p>',
  headers: { 'X-Test': 'delivery-check' }
}).then(r => { console.log('SENT messageId=' + r.messageId + ' accepted=' + JSON.stringify(r.accepted)); })
.catch(e => { console.log('ERROR: ' + e.message + ' code=' + e.code); });
" 2>&1 | tail -20""", "Test send to info@tokenpay.space (self)"),

    # 4. Check what happens when sending to gmail
    ("""docker exec tokenpay-id-api node -e "
const nodemailer = require('nodemailer');
const transporter = nodemailer.createTransport({
  host: 'smtp.timeweb.ru', port: 465, secure: true,
  auth: { user: 'info@tokenpay.space', pass: '1cgukl9kh5' }
});
transporter.sendMail({
  from: 'TOKEN PAY ID <info@tokenpay.space>',
  to: 'ichernykh08@gmail.com',
  subject: 'TEST ' + new Date().toISOString(),
  html: '<h1>Test delivery</h1><p>DNS SPF/DMARC check</p>',
}).then(r => { console.log('SENT OK: ' + r.messageId + ' response: ' + r.response); })
.catch(e => { console.log('SMTP ERROR: ' + e.message); });
" 2>&1""", "Test send to Gmail"),

    # 5. Check if timeweb SMTP accepts and delivers (check response code)
    ("openssl s_client -connect smtp.timeweb.ru:465 -quiet 2>/dev/null <<< '' | head -3", "SMTP TLS banner"),

    # 6. Check if IP is blacklisted
    ("host $(curl -s4 ifconfig.me) 2>/dev/null | head -3; curl -s https://api.blocklist.de/api.php?ip=$(curl -s4 ifconfig.me) 2>/dev/null | head -1", "Server IP blacklist check"),

    # 7. Check if Timeweb has relay issues
    ("dig +short MX tokenpay.space @8.8.8.8", "MX records"),
    ("dig +short A smtp.timeweb.ru @8.8.8.8", "SMTP server IP"),

    # 8. Check email template and from header
    ("docker exec tokenpay-id-api node -e \"const e=require('./email-service.js'); console.log('FROM_NAME:', process.env.SMTP_FROM || 'info@tokenpay.space'); console.log('initialized:', !!e);\" 2>&1", "Email service config"),

    # 9. Check container restart / recent start time
    ("docker inspect tokenpay-id-api --format '{{.State.StartedAt}}'", "API container start time"),
    ("date", "Server time"),

    # 10. Check .env on server
    ("cat /root/tokenpay-id/.env | grep -v '^#' | grep -v '^$'", "Full .env (no comments)"),
]

for cmd, label in cmds:
    print(f"\n{'='*50}")
    print(f"[{label}]")
    print('='*50)
    _, so, se = ssh.exec_command(cmd, timeout=30)
    out = so.read().decode().strip()
    err = se.read().decode().strip()
    result = out or err
    print(result or "(empty/no output)")

ssh.close()

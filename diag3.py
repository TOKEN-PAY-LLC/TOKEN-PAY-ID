import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('5.23.54.205', username='root', password='vE^6t-zFS3dpNT', timeout=20)

print("=" * 60)
print("EMAIL ROOT CAUSE ANALYSIS")
print("=" * 60)

cmds = [
    # 1. DNS status
    ("dig +short TXT tokenpay.space @8.8.8.8", "SPF"),
    ("dig +short TXT _dmarc.tokenpay.space @8.8.8.8", "DMARC"),
    # Check ALL possible DKIM selectors
    ("for sel in default mail dkim timeweb selector1 selector2 google k1 s1 s2 smtp email; do r=$(dig +short TXT ${sel}._domainkey.tokenpay.space @8.8.8.8 2>/dev/null); [ -n \"$r\" ] && echo \"FOUND DKIM: $sel -> $r\"; done; echo 'scan done'", "DKIM selectors"),

    # 2. Check real user registration emails in logs (all time)
    ("docker logs tokenpay-id-api 2>&1 | grep -i '\\[EMAIL\\] Sent' | grep -v 'info@tokenpay\\|ichernykh' | tail -20", "Emails to real users"),
    ("docker logs tokenpay-id-api 2>&1 | grep -i '\\[EMAIL\\]' | tail -50", "All email logs (last 50)"),

    # 3. Check actual delivery to yandex/mail.ru (common Russian providers)
    ("""docker exec tokenpay-id-api node -e "
const n=require('nodemailer');
const t=n.createTransport({host:'smtp.timeweb.ru',port:465,secure:true,auth:{user:'info@tokenpay.space',pass:'1cgukl9kh5'}});
t.sendMail({
  from:'TOKEN PAY ID <info@tokenpay.space>',
  to:'ichernykh08@gmail.com',
  subject:'КОД ПОДТВЕРЖДЕНИЯ — 123456',
  html:'<p>Ваш код: <b>123456</b></p><p>Код действителен 10 минут.</p>',
  headers:{'X-Mailer':'TokenPayID/2.0'}
}).then(r=>console.log('OK:',r.messageId,'response:',r.response))
.catch(e=>console.log('ERR:',e.message))
" 2>&1""", "Send real-looking verification email to Gmail"),

    # 4. Check PTR record for sending IP
    ("SERVER_IP=$(curl -s4 https://ifconfig.me 2>/dev/null); echo Server IP: $SERVER_IP; host $SERVER_IP 2>/dev/null; dig +short PTR $(echo $SERVER_IP | awk -F. '{print $4\".\"$3\".\"$2\".\"$1\".in-addr.arpa\"}') @8.8.8.8 2>/dev/null", "PTR record for server IP"),
    ("dig +short PTR $(dig +short A smtp.timeweb.ru @8.8.8.8 | head -1 | awk -F. '{print $4\".\"$3\".\"$2\".\"$1\".in-addr.arpa\"}') @8.8.8.8 2>/dev/null; echo '---'; dig +short A smtp.timeweb.ru @8.8.8.8", "Timeweb SMTP PTR"),

    # 5. Check email-service.js FROM_NAME
    ("docker exec tokenpay-id-api node -e \"process.env.SMTP_USER='info@tokenpay.space'; const fs=require('fs'); const code=fs.readFileSync('./email-service.js','utf8'); const m=code.match(/FROM_NAME[^;]+/); console.log(m?m[0]:'not found');\" 2>&1 | head -5", "FROM_NAME in code"),
    ("docker exec tokenpay-id-api grep -E 'FROM_NAME|FROM_EMAIL|fromName|fromEmail' email-service.js | head -10", "Email from config"),

    # 6. Check if Timeweb has outgoing mail logs/queue
    ("docker exec tokenpay-id-api cat /etc/hosts 2>/dev/null | grep -v '^#'; hostname -f 2>/dev/null", "Container hostname"),

    # 7. Check if email bounces come back
    ("docker logs tokenpay-id-api 2>&1 | grep -iE 'bounce|reject|blacklist|spam|5[0-9][0-9] |4[0-9][0-9] ' | tail -10", "SMTP error responses"),

    # 8. Check server reverse IP and blacklists
    ("SERVER_IP=$(curl -s4 https://ifconfig.me 2>/dev/null); echo $SERVER_IP; curl -s \"https://api.abuseipdb.com/api/v2/check?ipAddress=$SERVER_IP\" -H 'Key: ' 2>/dev/null | head -3", "AbuseIPDB check"),

    # 9. What FROM address is actually used in real email templates
    ("docker exec tokenpay-id-api node -e \"require('./email-service.js'); setTimeout(()=>{},100)\" 2>&1 | head -5", "Email service init log"),

    # 10. Check Timeweb DKIM via their API (common endpoint)
    ("curl -sk https://timeweb.com/ru/community/articles/kak-nastroit-spf-dkim-i-dmarc-dlya-domennoy-pochty 2>/dev/null | grep -i 'dkim\\|selector' | head -5", "Timeweb DKIM docs"),
]

for cmd, label in cmds:
    print(f"\n--- {label} ---")
    _, so, se = ssh.exec_command(cmd, timeout=20)
    try:
        out = so.read().decode('utf-8', errors='replace').strip()
        err = se.read().decode('utf-8', errors='replace').strip()
    except Exception:
        out = "(timeout)"
        err = ""
    print(out or err or "(empty)")

ssh.close()

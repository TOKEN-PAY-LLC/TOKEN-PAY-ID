import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('5.23.54.205', username='root', password='vE^6t-zFS3dpNT', timeout=20)

print("=" * 60)
print("USER REGISTRATION + DMARC + DKIM INVESTIGATION")
print("=" * 60)

cmds = [
    # Check DMARC again from multiple DNS servers
    ("dig +short TXT _dmarc.tokenpay.space @8.8.8.8 2>/dev/null; echo '---8.8.8.8'", "DMARC from 8.8.8.8"),
    ("dig +short TXT _dmarc.tokenpay.space @1.1.1.1 2>/dev/null; echo '---1.1.1.1'", "DMARC from 1.1.1.1"),
    ("dig +short TXT _dmarc.tokenpay.space @9.9.9.9 2>/dev/null; echo '---9.9.9.9'", "DMARC from 9.9.9.9"),

    # Check if there are real users in DB
    ("docker exec tokenpay-id-api node -e \"\
const {Pool}=require('pg');\
const p=new Pool({connectionString:process.env.DATABASE_URL});\
p.query('SELECT COUNT(*) as cnt FROM users').then(r=>console.log('Total users:',r.rows[0].cnt)).catch(e=>console.log('DB error:',e.message)).finally(()=>p.end());\
\" 2>&1", "Total users in DB"),

    ("docker exec tokenpay-id-api node -e \"\
const {Pool}=require('pg');\
const p=new Pool({connectionString:process.env.DATABASE_URL});\
p.query('SELECT email, email_verified, created_at FROM users ORDER BY created_at DESC LIMIT 10').then(r=>{r.rows.forEach(u=>console.log(u.email,'verified:',u.email_verified,'created:',u.created_at));}).catch(e=>console.log('err:',e.message)).finally(()=>p.end());\
\" 2>&1", "Recent users (last 10)"),

    # Check full API logs for registration/login errors
    ("docker logs tokenpay-id-api --since=24h 2>&1 | grep -iE 'register|login|send.code|email' | tail -40", "Auth + email API logs (24h)"),

    # Check if there are any email errors we missed
    ("docker logs tokenpay-id-api 2>&1 | grep -iE 'email.*error|error.*email|smtp|sendmail' | tail -20", "All SMTP/email errors ever"),

    # Check Timeweb SMTP headers - get DKIM selector from actual sent email
    ("docker exec tokenpay-id-api node -e \"\
const n=require('nodemailer');\
const t=n.createTransport({host:'smtp.timeweb.ru',port:465,secure:true,auth:{user:'info@tokenpay.space',pass:'1cgukl9kh5'}});\
t.sendMail({from:'info@tokenpay.space',to:'info@tokenpay.space',subject:'DKIM test',html:'test'}).then(r=>{\
console.log('messageId:',r.messageId);\
console.log('response:',r.response);\
console.log('envelope:',JSON.stringify(r.envelope));\
}).catch(e=>console.log('err:',e.message));\
\" 2>&1", "Self-email DKIM test"),

    # Check if Timeweb adds DKIM automatically on their end
    ("dig +short TXT @ns1.timeweb.ru tokenpay.space 2>/dev/null; echo '---'", "SPF from Timeweb NS"),
    ("dig +short TXT @ns1.timeweb.ru _dmarc.tokenpay.space 2>/dev/null; echo '---'", "DMARC from Timeweb NS"),

    # Check Cloudflare zone - is DNS proxied?
    ("dig +short A tokenpay.space @8.8.8.8", "A record (should be 5.23.54.205)"),
    ("curl -sk https://tokenpay.space/api/v1/health 2>/dev/null | head -1", "API health check"),

    # Database URL check
    ("docker exec tokenpay-id-api printenv DATABASE_URL 2>/dev/null | sed 's/:.*@/:***@/'", "DB connection (masked)"),

    # Timeweb mail check - does info@tokenpay.space mailbox exist?
    ("dig +short MX tokenpay.space @8.8.8.8", "MX records"),
    ("telnet mx1.timeweb.ru 25 <<< 'QUIT' 2>/dev/null | head -3 || nc -z -w3 mx1.timeweb.ru 25 && echo 'MX reachable' || echo 'MX unreachable'", "MX reachability"),
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

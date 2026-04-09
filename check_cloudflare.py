"""Check Cloudflare DNS for tokenpay.space and add missing SPF/DMARC records"""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('5.23.54.205', username='root', password='vE^6t-zFS3dpNT', timeout=15)

cmds = [
    # Check current DNS records
    ("dig +short TXT tokenpay.space @8.8.8.8", "SPF record"),
    ("dig +short TXT _dmarc.tokenpay.space @8.8.8.8", "DMARC record"),
    ("dig +short TXT default._domainkey.tokenpay.space @8.8.8.8", "DKIM (default)"),
    ("dig +short TXT timeweb._domainkey.tokenpay.space @8.8.8.8", "DKIM (timeweb)"),
    # Check if there's a Cloudflare API token in env or config files
    ("grep -r 'CLOUDFLARE\\|CF_API\\|CF_TOKEN\\|cf_token' /root/tokenpay-id/.env 2>/dev/null", "CF token in .env"),
    ("cat /root/tokenpay-id/.env | grep -i 'cloud\\|CF_' 2>/dev/null", "CF vars in .env"),
    # Check Timeweb panel for DKIM
    ("dig +short TXT dkim._domainkey.tokenpay.space @8.8.8.8", "DKIM (dkim)"),
    ("dig +short TXT mail._domainkey.tokenpay.space @8.8.8.8", "DKIM (mail)"),
    # Test sending email and check headers
    ("docker exec tokenpay-id-api node -e \"" +
     "const n=require('nodemailer');" +
     "const t=n.createTransport({host:'smtp.timeweb.ru',port:465,secure:true,auth:{user:'info@tokenpay.space',pass:'1cgukl9kh5'}});" +
     "t.verify().then(()=>console.log('SMTP verify OK')).catch(e=>console.log('SMTP verify FAIL:',e.message));" +
     "\" 2>&1", "SMTP verify"),
]

for cmd, label in cmds:
    print(f"\n--- {label} ---")
    _, so, se = ssh.exec_command(cmd, timeout=15)
    out = so.read().decode().strip()
    err = se.read().decode().strip()
    print(out or err or "(empty)")

ssh.close()

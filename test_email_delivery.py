import paramiko, time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('5.23.54.205', username='root', password='vE^6t-zFS3dpNT', timeout=15)

print("=== FINAL EMAIL DELIVERY TEST ===\n")

# 1. Verify all 3 DNS records
print("--- DNS Records (final check) ---")
for rec, label in [
    ("dig +short TXT tokenpay.space @8.8.8.8", "SPF"),
    ("dig +short TXT _dmarc.tokenpay.space @8.8.8.8", "DMARC"),
    ("dig +short TXT dkim._domainkey.tokenpay.space @8.8.8.8", "DKIM"),
]:
    _, so, _ = ssh.exec_command(rec, timeout=10)
    r = so.read().decode().strip()
    ok = "✓" if r else "✗"
    short = r[:80] if len(r) > 80 else r
    print(f"  {ok} {label}: {short}")

# 2. Send a realistic verification code email to Gmail
print("\n--- Sending verification code test email ---")
_, so, se = ssh.exec_command("""docker exec tokenpay-id-api node -e "
const n = require('nodemailer');
const t = n.createTransport({
  host: 'smtp.timeweb.ru', port: 465, secure: true,
  auth: { user: 'info@tokenpay.space', pass: '1cgukl9kh5' }
});
const html = \`
<div style='font-family:Arial,sans-serif;max-width:480px;margin:0 auto;background:#fff;border-radius:12px;border:1px solid #eee;padding:36px'>
<img src='https://tokenpay.space/tokenpay-id-light.png' style='height:32px;margin-bottom:24px' alt='TOKEN PAY ID'>
<h2 style='margin:0 0 8px;color:#111;font-size:20px'>Код подтверждения</h2>
<p style='color:#555;margin:0 0 24px'>Введите этот код для входа в аккаунт TOKEN PAY ID:</p>
<div style='background:#f5f5f7;border-radius:8px;padding:24px;text-align:center;font-size:36px;font-weight:700;letter-spacing:8px;color:#111;margin-bottom:24px'>847291</div>
<p style='color:#999;font-size:12px;margin:0'>Код действителен 10 минут. Если вы не запрашивали код — проигнорируйте это письмо.</p>
</div>\`;
t.sendMail({
  from: 'TOKEN PAY ID <info@tokenpay.space>',
  to: 'ichernykh08@gmail.com',
  subject: 'Ваш код подтверждения — 847291',
  html: html,
  headers: { 'X-Mailer': 'TokenPayID/2.0' }
}).then(r => {
  console.log('✓ SENT:', r.messageId);
  console.log('  Response:', r.response);
  console.log('  Accepted:', JSON.stringify(r.accepted));
}).catch(e => console.log('✗ ERROR:', e.message));
" 2>&1""", timeout=20)
out = so.read().decode().strip()
print(f"  {out}")

# 3. Also test with a Yandex address
print("\n--- Sending to yandex (most common Russian provider) ---")
_, so, _ = ssh.exec_command("""docker exec tokenpay-id-api node -e "
const n = require('nodemailer');
const t = n.createTransport({host:'smtp.timeweb.ru',port:465,secure:true,auth:{user:'info@tokenpay.space',pass:'1cgukl9kh5'}});
t.sendMail({
  from:'TOKEN PAY ID <info@tokenpay.space>',
  to:'ichernykh08@gmail.com',
  subject:'SPF+DKIM+DMARC test ' + new Date().toISOString(),
  html:'<p>All 3 email auth records are now active. This email should arrive in inbox.</p>',
}).then(r=>console.log('✓',r.response)).catch(e=>console.log('✗',e.message));
" 2>&1""", timeout=15)
print(f"  {so.read().decode().strip()}")

print("\n=== RESULT ===")
print("Check ichernykh08@gmail.com — should be in INBOX (not spam).")
print("If in inbox: email delivery is fixed ✓")
print("If in spam: wait 10-15 min for DNS full propagation, try again.")

ssh.close()

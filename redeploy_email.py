import paramiko, time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('5.23.54.205', username='root', password='vE^6t-zFS3dpNT', timeout=15)

def run(cmd, timeout=20):
    _, o, e = ssh.exec_command(cmd, timeout=timeout)
    out = o.read().decode().strip()
    err = e.read().decode().strip()
    if out: print("OUT:", out[:800])
    if err and 'warning' not in err.lower(): print("ERR:", err[:400])
    return out, err

sftp = ssh.open_sftp()
sftp.put(r'C:\Users\user\Desktop\TokenPay-Website\backend\email-service.js', '/tmp/email-service.js')
run("docker cp /tmp/email-service.js tokenpay-id-api:/app/email-service.js")
sftp.close()

run("docker restart tokenpay-id-api")
time.sleep(6)
run("docker ps --filter name=tokenpay-id-api --format '{{.Status}}'")

# Quick sanity check
js = r"""
const es = require('./email-service');
es.initTransporter();
const tpl = es.templates.verificationCode('Иван', '847291', 10, 'ru');
const preOK = tpl.html.includes('\u0412\u0430\u0448 \u043a\u043e\u0434') || tpl.html.includes('Your verification');
const sizeOK = tpl.html.includes('font-size:30px');
const bgOK = tpl.html.includes('background-color:#0c0c10;padding:36px 40px 28px');
const tableBox = tpl.html.includes('<table role="presentation"') && tpl.html.includes('5c5cff');
const noRawCode = !tpl.html.startsWith('847291') && !(tpl.html.indexOf('847291') < 200);
console.log('preheader descriptive:', preOK);
console.log('code 30px:', sizeOK);
console.log('body_ has bg:', bgOK);
console.log('codeBox is table:', tableBox);
console.log('preheader not raw code:', noRawCode);
console.log('has plaintext:', tpl.text.includes('847291'));
// Send real test
es.sendEmail('ichernykh08@gmail.com', '\u0422\u0435\u0441\u0442 \u043a\u043e\u0434\u0430 \u2014 TOKEN PAY ID', tpl)
  .then(r => console.log('SENT:', r.messageId || 'ok'))
  .catch(e => console.error('ERR:', e.message));
"""

sftp2 = ssh.open_sftp()
with sftp2.open('/tmp/chk.js', 'w') as f:
    f.write(js)
sftp2.close()

run("docker cp /tmp/chk.js tokenpay-id-api:/app/chk.js")
run("docker exec -w /app tokenpay-id-api node /app/chk.js", timeout=30)

ssh.close()
print("Done.")

import paramiko, json

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('5.23.54.205', username='root', password='vE^6t-zFS3dpNT', timeout=15)

def run(cmd, timeout=20):
    _, o, e = ssh.exec_command(cmd, timeout=timeout)
    out = o.read().decode().strip()
    err = e.read().decode().strip()
    if out: print("OUT:", out[:600])
    if err and 'warning' not in err.lower(): print("ERR:", err[:400])
    return out, err

# Check container health
run("docker ps --filter name=tokenpay-id-api --format '{{.Status}}'")
run("docker logs tokenpay-id-api --tail 20 2>&1")

# Send test email via the API's /api/v1/admin/test-email endpoint or directly via node
js = r"""
const es = require('./email-service');
es.initTransporter();
const tpl = es.templates.verificationCode('Тест', '123456', 10, 'ru');
console.log('Has html:', typeof tpl.html === 'string' && tpl.html.length > 100);
console.log('Has text:', typeof tpl.text === 'string' && tpl.text.length > 10);
console.log('HTML has inline style:', tpl.html.includes('background-color:#0c0c10'));
console.log('HTML has NO style tag classes:', !tpl.html.includes('class="cb"'));
console.log('Text snippet:', tpl.text.substring(0, 80));
// Send real test
es.sendEmail(
  'ichernykh08@gmail.com',
  'Тест письма — TOKEN PAY ID',
  tpl
).then(r => console.log('SENT OK:', r.messageId || r.accepted))
 .catch(e => console.error('SEND ERR:', e.message));
"""

sftp = ssh.open_sftp()
with sftp.open('/tmp/test_email.js', 'w') as f:
    f.write(js)
sftp.close()

run("docker cp /tmp/test_email.js tokenpay-id-api:/app/test_email.js")
run("docker exec -w /app tokenpay-id-api node /app/test_email.js", timeout=30)

ssh.close()

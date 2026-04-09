import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('5.23.54.205', username='root', password='vE^6t-zFS3dpNT')

print('=== Dashboard QR pre-approve check ===')
i, o, e = ssh.exec_command("grep -n 'login-confirm' /root/tokenpay-id/frontend/dashboard.html")
print(o.read().decode())

print('=== QR-login autoLogin check ===')
i, o, e = ssh.exec_command("grep -n 'autoLogin' /root/tokenpay-id/frontend/qr-login.html")
print(o.read().decode())

print('=== Email headers check (should be 0 Precedence lines) ===')
i, o, e = ssh.exec_command("grep -c 'Precedence' /root/tokenpay-id/backend/email-service.js")
print(o.read().decode())

print('=== Dashboard QR description ===')
i, o, e = ssh.exec_command("grep -o 'data-ru=\"[^\"]*QR[^\"]*\"' /root/tokenpay-id/frontend/dashboard.html | head -3")
print(o.read().decode())

ssh.close()

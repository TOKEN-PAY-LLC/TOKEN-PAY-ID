import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('5.23.54.205', username='root', password='vE^6t-zFS3dpNT', timeout=15)

cmds = [
    # 1. Check SMTP env vars in the container
    ("docker exec tokenpay-id-api printenv | grep -i SMTP", "SMTP env vars"),
    # 2. Check email logs
    ("docker logs tokenpay-id-api 2>&1 | grep -i '\\[EMAIL\\]' | tail -30", "Email logs (last 30)"),
    # 3. Check for SMTP errors
    ("docker logs tokenpay-id-api 2>&1 | grep -i 'error.*email\\|email.*error\\|smtp.*error\\|error.*smtp' | tail -20", "SMTP errors"),
    # 4. Check .env file for SMTP settings
    ("cat /root/tokenpay-id/.env 2>/dev/null | grep -i SMTP", "SMTP in .env"),
    # 5. Check docker-compose env
    ("cat /root/tokenpay-id/docker-compose.yml 2>/dev/null | grep -i smtp", "SMTP in compose"),
    # 6. Test SMTP connection from server
    ("python3 -c \"import socket; s=socket.create_connection(('smtp.timeweb.ru', 465), 5); print('SMTP reachable'); s.close()\" 2>&1", "SMTP reachability"),
    # 7. Check if any emails were sent successfully
    ("docker logs tokenpay-id-api 2>&1 | grep -i 'Sent to' | tail -10", "Emails sent"),
    # 8. Check container uptime
    ("docker ps --format '{{.Names}}: {{.Status}}'", "Container status"),
    # 9. Check DNS for mail records
    ("dig +short MX tokenpay.space 2>/dev/null || nslookup -type=MX tokenpay.space 2>/dev/null | head -5", "MX records"),
    # 10. Check SPF/DKIM
    ("dig +short TXT tokenpay.space 2>/dev/null | head -10", "TXT/SPF records"),
]

print("=" * 60)
print("TOKENPAY EMAIL DIAGNOSIS")
print("=" * 60)

for cmd, label in cmds:
    print(f"\n--- {label} ---")
    _, so, se = ssh.exec_command(cmd)
    out = so.read().decode().strip()
    err = se.read().decode().strip()
    print(out or err or "(empty)")

ssh.close()

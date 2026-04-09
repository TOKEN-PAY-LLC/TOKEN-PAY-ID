import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('5.23.54.205', username='root', password='vE^6t-zFS3dpNT', timeout=20)

print("=" * 60)
print("API ROUTING + NGINX + DKIM INVESTIGATION")
print("=" * 60)

cmds = [
    # 1. Check nginx config
    ("docker exec tokenpay-id-nginx cat /etc/nginx/conf.d/default.conf 2>/dev/null", "Nginx config"),

    # 2. Direct API check (bypass nginx)
    ("docker inspect tokenpay-id-api --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' 2>/dev/null", "API container IP"),
    ("docker exec tokenpay-id-nginx curl -sk http://api:3000/api/v1/health 2>/dev/null | head -3", "API direct (via Docker network)"),
    ("docker exec tokenpay-id-api curl -sk http://localhost:3000/api/v1/health 2>/dev/null | head -3", "API on localhost:3000"),

    # 3. Check if API is listening on the right port
    ("docker exec tokenpay-id-api ss -tlnp 2>/dev/null || docker exec tokenpay-id-api netstat -tlnp 2>/dev/null | head -5", "API listening ports"),

    # 4. Check DB tables (find the correct path)
    ("docker exec tokenpay-id-api ls /app/ 2>/dev/null | head -20", "App directory listing"),
    ("docker exec tokenpay-id-api printenv | grep -E 'DATABASE|POSTGRES|DB_' | head -5", "DB env vars"),

    # 5. Check last 100 API request logs
    ("docker logs tokenpay-id-api --since=24h 2>&1 | grep -vE '\\[EMAIL\\]|DEBUG|INFO' | tail -40", "API request logs (24h, no email)"),

    # 6. Count total API calls to auth endpoints
    ("docker logs tokenpay-id-api 2>&1 | grep -cE 'POST /api/v1/auth|GET /api/v1/auth' 2>/dev/null || echo 'no request logs'", "Auth API call count"),

    # 7. Check if any users ever registered
    ("docker exec tokenpay-id-api node -e \"\
try{\
  const db=require('./database');\
  console.log('db module found:', typeof db);\
}catch(e){console.log('db module error:',e.message);}\
\" 2>&1", "DB module check"),

    # 8. External API check
    ("curl -sk https://tokenpay.space/api/v1/health -w '\\nHTTP:%{http_code}' 2>/dev/null | tail -2", "External API health"),
    ("curl -sk -X POST https://tokenpay.space/api/v1/auth/send-code -H 'Content-Type: application/json' -d '{\"email\":\"test@example.com\",\"type\":\"register\"}' -w '\\nHTTP:%{http_code}' 2>/dev/null | tail -3", "Send-code API test"),

    # 9. Check DKIM - try to find Timeweb DKIM selector by sending email and reading headers
    # First, check if we can get headers from info@tokenpay.space
    ("dig +short TXT selector1._domainkey.tokenpay.space @ns1.timeweb.ru 2>/dev/null; dig +short TXT selector2._domainkey.tokenpay.space @ns1.timeweb.ru 2>/dev/null; echo 'done'", "DKIM selectors from Timeweb NS"),

    # 10. Try to get DKIM key from Timeweb API
    ("curl -sk 'https://timeweb.com/api/v2/mail-boxes?domain=tokenpay.space' -H 'Authorization: Bearer ' 2>/dev/null | head -5 || echo 'no timeweb API access'", "Timeweb API DKIM"),
]

for cmd, label in cmds:
    print(f"\n--- {label} ---")
    _, so, se = ssh.exec_command(cmd, timeout=20)
    try:
        out = so.read().decode('utf-8', errors='replace').strip()
        err = se.read().decode('utf-8', errors='replace').strip()
    except Exception as e:
        out = f"(timeout: {e})"
        err = ""
    print(out or err or "(empty)")

ssh.close()

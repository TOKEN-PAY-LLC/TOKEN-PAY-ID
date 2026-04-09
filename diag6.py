import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('5.23.54.205', username='root', password='vE^6t-zFS3dpNT', timeout=20)

print("=== FOCUSED API + DKIM CHECK ===\n")

cmds = [
    # Is API actually working?
    ("curl -sk https://tokenpay.space/api/v1/health -w '\nHTTP:%{http_code}' | tail -3", "API health external"),
    ("curl -sk -X POST https://tokenpay.space/api/v1/auth/send-code -H 'Content-Type: application/json' -d '{\"email\":\"diag@test.com\",\"type\":\"register\"}' -w '\nHTTP:%{http_code}' | tail -3", "send-code API (register)"),
    ("docker exec tokenpay-id-nginx cat /etc/nginx/conf.d/default.conf | grep -A3 'location /api'", "Nginx API routing"),
    ("docker exec tokenpay-id-api curl -sk http://localhost:3000/api/v1/health | head -2", "API local port 3000"),
    ("docker exec tokenpay-id-api printenv PORT 2>/dev/null || docker exec tokenpay-id-api grep -r 'listen\\|PORT' /app/server.js 2>/dev/null | head -5", "API port config"),

    # DKIM from Timeweb's own nameserver
    ("dig +short TXT tokenpay.space @ns1.timeweb.ru 2>/dev/null", "All TXT from Timeweb NS"),
    ("dig +short TXT _dmarc.tokenpay.space @ns1.timeweb.ru 2>/dev/null", "DMARC from Timeweb NS"),
    ("for sel in mail selector1 selector2 timeweb dkim default k1; do r=$(dig +short TXT ${sel}._domainkey.tokenpay.space @ns1.timeweb.ru 2>/dev/null); [ -n \"$r\" ] && echo \"$sel: $r\"; done; echo done", "DKIM from Timeweb NS"),

    # Check full API logs (last 100 lines including requests)
    ("docker logs tokenpay-id-api --tail=100 2>&1 | grep -v '\\[2026\\]\\|DEBUG\\|verbose' | head -60", "Recent API logs"),

    # Check how many users registered
    ("docker exec tokenpay-id-api node -e 'const db=require(\"./database\"); db.query(\"SELECT count(*) from users\").then(r=>console.log(JSON.stringify(r.rows))).catch(e=>console.log(e.message))' 2>&1 | tail -3", "User count (v1)"),
    ("docker exec tokenpay-id-api find /app -name '*.db' -o -name '*.sqlite' 2>/dev/null | head -5", "SQLite files"),
    ("docker exec tokenpay-id-api ls /app 2>/dev/null", "App files"),
]

for cmd, label in cmds:
    print(f"--- {label} ---")
    _, so, se = ssh.exec_command(cmd, timeout=15)
    try:
        out = so.read().decode('utf-8', errors='replace').strip()[:800]
        err = se.read().decode('utf-8', errors='replace').strip()[:200]
    except Exception:
        out, err = "(timeout)", ""
    print(out or err or "(empty)")
    print()

ssh.close()

#!/usr/bin/env python3
"""Quick verification - single SSH command batch"""
import paramiko

SERVER = "5.23.54.205"
USER = "root"
PASSWORD = "vE^6t-zFS3dpNT"

def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(SERVER, port=22, username=USER, password=PASSWORD,
              timeout=120, banner_timeout=120, auth_timeout=120,
              allow_agent=False, look_for_keys=False)
    transport = c.get_transport()
    if transport:
        transport.set_keepalive(15)

    # Run all checks in one command to avoid connection issues
    cmd = """
echo "=== DOCKER ==="
docker ps --format '{{.Names}}: {{.Status}}'
echo ""
echo "=== NGINX CONFIG ==="
docker exec tokenpay-id-nginx nginx -t 2>&1
echo ""
echo "=== SUBDOMAIN ROUTING ==="
echo -n "tokenpay.space: "; docker exec tokenpay-id-nginx curl -sk -H 'Host: tokenpay.space' https://localhost/ 2>/dev/null | grep -oP '(?<=<title>).*?(?=</title>)'
echo -n "auth.tokenpay.space: "; docker exec tokenpay-id-nginx curl -sk -H 'Host: auth.tokenpay.space' https://localhost/ 2>/dev/null | grep -oP '(?<=<title>).*?(?=</title>)'
echo -n "id.tokenpay.space: "; docker exec tokenpay-id-nginx curl -sk -H 'Host: id.tokenpay.space' https://localhost/ 2>/dev/null | grep -oP '(?<=<title>).*?(?=</title>)'
echo ""
echo "=== KEY FILES ==="
for f in index.html login.html dashboard.html styles.css script.js theme-init.js qrcode-min.js oauth-consent.html docs.html admin.html privacy.html terms.html sdk/tokenpay-auth.js register.html; do
  test -f /root/tokenpay-id/frontend/$f && echo "[OK] $f" || echo "[MISS] $f"
done
echo ""
echo "=== THEME-INIT IN HEAD ==="
head -20 /root/tokenpay-id/frontend/login.html | grep -c theme-init | xargs -I{} echo "login.html: {} matches"
head -22 /root/tokenpay-id/frontend/register.html | grep -c theme-init | xargs -I{} echo "register.html: {} matches"
echo ""
echo "=== PAGE REVEAL CSS ==="
grep -c pageReveal /root/tokenpay-id/frontend/styles.css | xargs -I{} echo "pageReveal rules: {}"
echo ""
echo "=== API HEALTH ==="
docker exec tokenpay-id-nginx curl -sk https://localhost/health 2>/dev/null
echo ""
echo "=== DONE ==="
"""
    stdin, stdout, stderr = c.exec_command(cmd)
    stdout.channel.recv_exit_status()
    print(stdout.read().decode())
    c.close()

if __name__ == "__main__":
    main()

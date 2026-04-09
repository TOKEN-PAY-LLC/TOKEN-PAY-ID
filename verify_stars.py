#!/usr/bin/env python3
"""Verify star sky and welcome page specifics"""
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

    cmd = """
echo "=== StarSky in script.js ==="
grep -c 'class StarSky' /root/tokenpay-id/frontend/script.js | xargs -I{} echo "StarSky class: {} match"
grep -c 'ParticleSystem' /root/tokenpay-id/frontend/script.js | xargs -I{} echo "ParticleSystem (should be 0): {} match"
echo ""
echo "=== welcome.html exists ==="
test -f /root/tokenpay-id/frontend/welcome.html && echo "[OK] welcome.html" || echo "[FAIL] welcome.html"
echo ""
echo "=== welcome.html title ==="
grep -oP '(?<=<title>).*?(?=</title>)' /root/tokenpay-id/frontend/welcome.html
echo ""
echo "=== Glow halos (should be 0) ==="
grep -c 'glow\|Glow\|r \* 2.5' /root/tokenpay-id/frontend/script.js || echo "0"
echo ""
echo "=== Dashboard theme check ==="
grep -c 'classList.contains' /root/tokenpay-id/frontend/dashboard.html | xargs -I{} echo "Theme checks: {}"
echo ""
echo "=== Star params in script.js (first 20 lines) ==="
head -30 /root/tokenpay-id/frontend/script.js
echo ""
echo "=== Light theme canvas opacity ==="
grep 'particles.*opacity' /root/tokenpay-id/frontend/styles.css
echo ""
echo "=== Nginx map for auth ==="
grep 'auth.tokenpay' /root/tokenpay-id/nginx/nginx.conf
echo ""
echo "=== DONE ==="
"""
    stdin, stdout, stderr = c.exec_command(cmd)
    stdout.channel.recv_exit_status()
    print(stdout.read().decode())
    c.close()

if __name__ == "__main__":
    main()

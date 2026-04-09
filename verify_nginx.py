#!/usr/bin/env python3
"""Verify nginx subdomain routing from inside the server"""
import paramiko

SERVER = "5.23.54.205"
USER = "root"
PASSWORD = "vE^6t-zFS3dpNT"

def run_cmd(client, cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    stdout.channel.recv_exit_status()
    return stdout.read().decode().strip()

def main():
    print("Connecting...")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(SERVER, port=22, username=USER, password=PASSWORD,
              timeout=120, banner_timeout=120, auth_timeout=120,
              allow_agent=False, look_for_keys=False)

    # Check nginx config
    print("\n=== Nginx config (location blocks) ===")
    out = run_cmd(c, "docker exec tokenpay-id-nginx cat /etc/nginx/conf.d/default.conf | grep -A3 'location'")
    print(out[:1000])

    # Curl from inside container
    print("\n=== curl auth.tokenpay.space (title) ===")
    out = run_cmd(c, "docker exec tokenpay-id-nginx curl -sk -H 'Host: auth.tokenpay.space' https://localhost/ 2>/dev/null | grep -i '<title>'")
    print(out or "(no title found)")

    print("\n=== curl id.tokenpay.space (title) ===")
    out = run_cmd(c, "docker exec tokenpay-id-nginx curl -sk -H 'Host: id.tokenpay.space' https://localhost/ 2>/dev/null | grep -i '<title>'")
    print(out or "(no title found)")

    print("\n=== curl tokenpay.space (title) ===")
    out = run_cmd(c, "docker exec tokenpay-id-nginx curl -sk -H 'Host: tokenpay.space' https://localhost/ 2>/dev/null | grep -i '<title>'")
    print(out or "(no title found)")

    # Check if login.html exists
    print("\n=== File check ===")
    out = run_cmd(c, "docker exec tokenpay-id-nginx ls -la /usr/share/nginx/html/login.html /usr/share/nginx/html/dashboard.html /usr/share/nginx/html/index.html 2>&1")
    print(out)

    c.close()

if __name__ == "__main__":
    main()

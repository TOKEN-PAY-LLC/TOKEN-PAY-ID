#!/usr/bin/env python3
"""Final verification of TokenPay deployment"""
import paramiko
import json
import sys

SERVER = "5.23.54.205"
USER = "root"
PASSWORD = "vE^6t-zFS3dpNT"

def run_cmd(client, cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    stdout.channel.recv_exit_status()
    return stdout.read().decode().strip(), stderr.read().decode().strip()

def main():
    print("=" * 60)
    print("TokenPay Final Verification")
    print("=" * 60)

    print("\n[1] Connecting...")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(SERVER, port=22, username=USER, password=PASSWORD,
              timeout=120, banner_timeout=120, auth_timeout=120,
              allow_agent=False, look_for_keys=False)
    print("    OK")

    ok = True

    print("\n[2] Docker containers...")
    out, _ = run_cmd(c, "docker ps --format '{{.Names}}: {{.Status}}'")
    for line in out.split("\n"):
        if line.strip():
            s = "+" if "Up" in line else "FAIL"
            print(f"    [{s}] {line.strip()}")
            if s == "FAIL":
                ok = False

    print("\n[3] Nginx config test...")
    out, err = run_cmd(c, "docker exec tokenpay-id-nginx nginx -t 2>&1")
    if "syntax is ok" in out:
        print("    [+] Syntax OK, no warnings" if "warn" not in out else "    [+] Syntax OK")
    else:
        print(f"    [FAIL] {out[:200]}")
        ok = False

    print("\n[4] Subdomain routing...")
    for host, expect in [("tokenpay.space", "TOKEN PAY LLC"), ("auth.tokenpay.space", "Войти"), ("id.tokenpay.space", "Личный кабинет")]:
        out, _ = run_cmd(c, f"docker exec tokenpay-id-nginx curl -sk -H 'Host: {host}' https://localhost/ 2>/dev/null | grep -oP '(?<=<title>).*?(?=</title>)'")
        if expect in out:
            print(f"    [+] {host} -> {out}")
        else:
            print(f"    [FAIL] {host} -> got '{out}', expected '{expect}'")
            ok = False

    print("\n[5] Key files...")
    files = ["index.html", "login.html", "register.html", "dashboard.html",
             "styles.css", "script.js", "theme-init.js", "qrcode-min.js",
             "oauth-consent.html", "docs.html", "admin.html", "privacy.html",
             "terms.html", "sdk/tokenpay-auth.js"]
    missing = []
    for f in files:
        out, _ = run_cmd(c, f"docker exec tokenpay-id-nginx test -f /usr/share/nginx/html/{f} && echo OK")
        if "OK" not in out:
            missing.append(f)
    if missing:
        for m in missing:
            print(f"    [FAIL] {m} MISSING")
        ok = False
    else:
        print(f"    [+] All {len(files)} files present")

    print("\n[6] API health...")
    out, _ = run_cmd(c, "docker exec tokenpay-id-nginx curl -sk https://localhost/health 2>/dev/null")
    try:
        h = json.loads(out)
        print(f"    [+] {h.get('status', 'unknown')}")
    except Exception:
        print(f"    [?] {out[:100]}")

    print("\n[7] Theme-init in login.html <head>...")
    out, _ = run_cmd(c, "docker exec tokenpay-id-nginx head -20 /usr/share/nginx/html/login.html | grep theme-init")
    if "theme-init" in out:
        print("    [+] theme-init.js in <head>")
    else:
        print("    [FAIL] theme-init.js NOT in <head>")
        ok = False

    print("\n[8] Page reveal CSS...")
    out, _ = run_cmd(c, "docker exec tokenpay-id-nginx grep 'pageReveal' /usr/share/nginx/html/styles.css")
    if "pageReveal" in out:
        print("    [+] Smooth page reveal animation present")
    else:
        print("    [FAIL] pageReveal missing from styles.css")
        ok = False

    c.close()

    print("\n" + "=" * 60)
    if ok:
        print("ALL CHECKS PASSED")
    else:
        print("SOME CHECKS FAILED")
    print("=" * 60)
    print("\n  https://tokenpay.space")
    print("  https://auth.tokenpay.space")
    print("  https://id.tokenpay.space\n")

if __name__ == "__main__":
    main()

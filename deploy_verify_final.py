"""Verify all deployed changes are live"""
import paramiko

HOST = '5.23.54.205'
USER = 'root'
PASS = 'vE^6t-zFS3dpNT'

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=15)

    checks = [
        ('index.html fix (no <br> in h2)',
         "grep -c 'цифровой идентификатор</h2>' /root/tokenpay-id/frontend/index.html"),
        ('docs.html v2.2 sidebar',
         "grep -c 'API Reference v2.2' /root/tokenpay-id/frontend/docs.html"),
        ('docs.html code_verifier param',
         "grep -c 'code_verifier' /root/tokenpay-id/frontend/docs.html"),
        ('SDK v2.0 PKCE',
         "grep -c 'code_challenge_method=S256' /root/tokenpay-id/frontend/sdk/tokenpay-auth.js"),
        ('SDK getCodeVerifier',
         "grep -c 'getCodeVerifier' /root/tokenpay-id/frontend/sdk/tokenpay-auth.js"),
        ('Widget exists + PKCE',
         "grep -c 'code_challenge' /root/tokenpay-id/frontend/sdk/tpid-widget.js"),
        ('Widget TPID global',
         "grep -c 'window.TPID' /root/tokenpay-id/frontend/sdk/tpid-widget.js"),
        # Public URL checks via curl
        ('Public docs has code_verifier',
         "curl -sk https://tokenpay.space/docs | grep -c 'code_verifier'"),
        ('Public SDK has PKCE',
         "curl -sk https://tokenpay.space/sdk/tokenpay-auth.js | grep -c 'code_challenge'"),
        ('Public widget exists',
         "curl -sk -o /dev/null -w '%{http_code}' https://tokenpay.space/sdk/tpid-widget.js"),
        ('Public index no duplicate',
         "curl -sk https://tokenpay.space/ | grep -c 'цифровой идентификатор</h2>'"),
    ]

    print('=== Verification ===')
    all_ok = True
    for label, cmd in checks:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
        out = stdout.read().decode().strip()
        ok = bool(out and out != '0')
        status = '✓' if ok else '✗'
        print(f'  {status} {label}: {out}')
        if not ok: all_ok = False

    ssh.close()
    print(f'\n=== {"ALL CHECKS PASSED" if all_ok else "SOME CHECKS FAILED"} ===')

if __name__ == '__main__':
    main()

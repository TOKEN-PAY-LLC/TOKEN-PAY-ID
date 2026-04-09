#!/usr/bin/env python3
"""Deploy updated nginx.conf - find host path and restart container"""
import paramiko

SERVER = "5.23.54.205"
USER = "root"
PASSWORD = "vE^6t-zFS3dpNT"

def run_cmd(client, cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    return exit_code, out, err

def main():
    print("[1/4] Connecting...")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(SERVER, port=22, username=USER, password=PASSWORD,
              timeout=120, banner_timeout=120, auth_timeout=120,
              allow_agent=False, look_for_keys=False)
    print("    Connected!")

    print("[2/4] Finding nginx config on host...")
    # Get mount source for nginx.conf
    inspect_fmt = "{{range .Mounts}}{{.Source}}|{{.Destination}}\\n{{end}}"
    code, out, err = run_cmd(c, f"docker inspect tokenpay-id-nginx --format '{inspect_fmt}'")
    print(f"    Mounts:\n{out}")

    # Find the compose project directory
    code2, out2, err2 = run_cmd(c, "docker inspect tokenpay-id-nginx --format '{{index .Config.Labels \"com.docker.compose.project.working_dir\"}}'")
    project_dir = out2.strip()
    print(f"    Compose project dir: {project_dir}")

    if not project_dir:
        # Fallback: search common locations
        code3, out3, _ = run_cmd(c, "find /root /opt /home -name 'docker-compose.yml' -path '*/TokenPay*' 2>/dev/null | head -3")
        print(f"    Searching for docker-compose.yml: {out3}")
        if out3:
            import os
            project_dir = os.path.dirname(out3.split('\n')[0])
        else:
            code4, out4, _ = run_cmd(c, "find / -maxdepth 4 -name 'docker-compose.yml' 2>/dev/null | head -5")
            print(f"    Broader search: {out4}")
            if out4:
                import os
                project_dir = os.path.dirname(out4.split('\n')[0])

    if not project_dir:
        print("    ERROR: Cannot find project directory!")
        c.close()
        return

    nginx_conf_path = project_dir + "/nginx/nginx.conf"
    print(f"    Target: {nginx_conf_path}")

    print("[3/4] Uploading new nginx.conf...")
    sftp = c.open_sftp()
    sftp.put("nginx/nginx.conf", nginx_conf_path)
    sftp.close()
    print("    Uploaded!")

    print("[4/4] Restarting nginx container...")
    code, out, err = run_cmd(c, "docker restart tokenpay-id-nginx")
    print(f"    Output: {out}")
    if err:
        print(f"    Stderr: {err[:300]}")

    # Verify
    code, out, err = run_cmd(c, "docker exec tokenpay-id-nginx nginx -t")
    print(f"    Config test: {err or out}")

    c.close()
    print("\nDone! Nginx config updated and container restarted.")

if __name__ == "__main__":
    main()

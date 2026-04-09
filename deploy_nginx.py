#!/usr/bin/env python3
"""Deploy updated nginx.conf to server and reload nginx in Docker"""
import paramiko
import time

SERVER = "5.23.54.205"
USER = "root"
PASSWORD = "vE^6t-zFS3dpNT"

def main():
    print("[1/3] Connecting to server...")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(SERVER, port=22, username=USER, password=PASSWORD,
              timeout=120, banner_timeout=120, auth_timeout=120,
              allow_agent=False, look_for_keys=False)
    print("    Connected!")

    print("[2/3] Uploading nginx.conf...")
    sftp = c.open_sftp()
    sftp.put("nginx/nginx.conf", "/tmp/nginx.conf.new")
    sftp.close()
    print("    Uploaded!")

    print("[3/3] Deploying nginx config...")
    commands = [
        "CONTAINER=$(docker ps --filter name=nginx --format '{{.Names}}' | head -1)",
        "echo \"Nginx container: $CONTAINER\"",
        "docker cp /tmp/nginx.conf.new $CONTAINER:/etc/nginx/conf.d/default.conf",
        "docker exec $CONTAINER nginx -t",
        "docker exec $CONTAINER nginx -s reload",
        "rm -f /tmp/nginx.conf.new",
        "echo DONE",
    ]
    cmd = " && ".join(commands)
    stdin, stdout, stderr = c.exec_command(cmd)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode()
    err = stderr.read().decode()
    print("    Output:", out)
    if err:
        print("    Stderr:", err[:500])
    if exit_code == 0:
        print("    Nginx config deployed and reloaded!")
    else:
        print(f"    Exit code: {exit_code}")
    c.close()

if __name__ == "__main__":
    main()

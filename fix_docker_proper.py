#!/usr/bin/env python3
"""Proper Docker fix: find compose config, fix networking, update API container"""
import paramiko, time

SERVER = "5.23.54.205"
USER = "root"
PASSWORD = "vE^6t-zFS3dpNT"

def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(SERVER, port=22, username=USER, password=PASSWORD,
              timeout=60, banner_timeout=60, auth_timeout=60,
              allow_agent=False, look_for_keys=False)
    return c

def run(client, cmd, show=True):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=120)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    code = stdout.channel.recv_exit_status()
    if show:
        if out:
            for line in out.split('\n')[:50]: print("  " + line)
        if err:
            for line in err.split('\n')[:10]: print("  ERR: " + line)
    return out, err, code

client = connect()
print("Connected.\n")

# --- 1. Find docker-compose file ---
print("=== DOCKER COMPOSE FILE ===")
run(client, "find / -name 'docker-compose.yml' -o -name 'docker-compose.yaml' 2>/dev/null | grep -v proc | head -5")
out, _, _ = run(client, "find / -name 'docker-compose*' 2>/dev/null | grep -v proc | head -5", show=False)
compose_paths = [p.strip() for p in out.split('\n') if p.strip()]
for p in compose_paths:
    print(f"  Found: {p}")
    run(client, f"cat {p}")

# --- 2. Inspect Docker network and containers ---
print("\n=== DOCKER NETWORK INSPECT ===")
run(client, "docker network ls 2>/dev/null")
run(client, "docker inspect tokenpay-id-api 2>/dev/null | python3 -c \"import json,sys; d=json.load(sys.stdin)[0]; n=d.get('NetworkSettings',{}); print('Networks:', list(n.get('Networks',{}).keys())); print('IP:', n.get('IPAddress','')); env=d.get('Config',{}).get('Env',[]); [print('ENV:', e) for e in env if any(k in e for k in ['DB','PORT','JWT','ADMIN'])]\" 2>/dev/null")

# --- 3. Check what port/address the API runs on inside container ---
print("\n=== API CONTAINER INSPECT ===")
run(client, """
API_CID=$(docker ps -q --filter name=tokenpay-id-api)
echo "API container ID: $API_CID"
docker inspect "$API_CID" 2>/dev/null | python3 -c "
import json, sys
d = json.load(sys.stdin)[0]
cfg = d.get('Config', {})
hcfg = d.get('HostConfig', {})
net = d.get('NetworkSettings', {})
print('Image:', cfg.get('Image',''))
print('Cmd:', cfg.get('Cmd',''))
print('Entrypoint:', cfg.get('Entrypoint',''))
print('ExposedPorts:', list(cfg.get('ExposedPorts', {}).keys()))
print('Networks:', list(net.get('Networks', {}).keys()))
for name, ninfo in net.get('Networks', {}).items():
    print(f'  Network {name}: IP={ninfo.get(\"IPAddress\",\"\")}, Aliases={ninfo.get(\"Aliases\",[])}')
envs = cfg.get('Env', [])
for e in envs:
    if any(k in e for k in ['DB_', 'PORT', 'JWT', 'NODE']):
        print('ENV:', e)
print('Binds:', hcfg.get('Binds', []))
" 2>/dev/null
""")

# --- 4. Check nginx container network and config ---
print("\n=== NGINX CONTAINER INSPECT ===")
run(client, """
NGINX_CID=$(docker ps -q --filter name=tokenpay-id-nginx)
echo "Nginx container ID: $NGINX_CID"
docker inspect "$NGINX_CID" 2>/dev/null | python3 -c "
import json, sys
d = json.load(sys.stdin)[0]
cfg = d.get('Config', {})
hcfg = d.get('HostConfig', {})
net = d.get('NetworkSettings', {})
for name, ninfo in net.get('Networks', {}).items():
    print(f'Network {name}: IP={ninfo.get(\"IPAddress\",\"\")}, Aliases={ninfo.get(\"Aliases\",[])}')
print('Binds:', hcfg.get('Binds', []))
" 2>/dev/null
echo "---"
docker exec "$NGINX_CID" cat /etc/nginx/conf.d/default.conf 2>/dev/null | grep -A5 'location.*api\|proxy_pass\|upstream'
""")

# --- 5. Get actual nginx full config inside Docker ---
print("\n=== NGINX FULL CONFIG (DOCKER) ===")
run(client, """
NGINX_CID=$(docker ps -q --filter name=tokenpay-id-nginx)
docker exec "$NGINX_CID" cat /etc/nginx/conf.d/default.conf 2>/dev/null || \
docker exec "$NGINX_CID" nginx -T 2>/dev/null | grep -E 'proxy_pass|upstream|server_name|listen' | head -20
""")

# --- 6. Revert nginx change back to 3000 if needed ---
print("\n=== REVERT NGINX 8080 -> ORIGINAL ===")
run(client, r"""
CONF="/etc/nginx/sites-available/tokenpay"
# Check what's there now
grep proxy_pass "$CONF" 2>/dev/null

# If we changed 3000 to 8080 on the HOST config, check if nginx container
# reads from /etc/nginx/sites-available or from its own config
NGINX_CID=$(docker ps -q --filter name=tokenpay-id-nginx)

# Check if container has the file mounted
docker exec "$NGINX_CID" ls /etc/nginx/sites-available/ 2>/dev/null
docker exec "$NGINX_CID" ls /etc/nginx/conf.d/ 2>/dev/null
docker exec "$NGINX_CID" ls /etc/nginx/sites-enabled/ 2>/dev/null
""")

client.close()
print("\nDone. Analysis complete.")

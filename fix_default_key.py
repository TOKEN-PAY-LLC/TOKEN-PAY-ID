import paramiko, time, urllib.request

# Quick HTTP check
try:
    r = urllib.request.urlopen('https://tokenpay.space/oauth-consent.html', timeout=8)
    print("oauth-consent.html HTTP:", r.status)
    content = r.read().decode()
    print("Has gradient header:", 'consent-header' in content)
    print("Has loading spinner:", 'consent-spinner' in content)
    print("Has brand gradient:", '6c63ff' in content)
    print("Has GENERIC filter:", '_GENERIC' in content)
    r2 = urllib.request.urlopen('https://tokenpay.space/dashboard.html', timeout=8)
    print("dashboard.html HTTP:", r2.status)
    c2 = r2.read().decode()
    print("Has step badges:", 'copyWebhookSecret' in c2)
    print("Has code example:", 'x-tpid-signature' in c2.lower())
except Exception as e:
    print("HTTP check error:", e)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('5.23.54.205', username='root', password='vE^6t-zFS3dpNT', timeout=15)

# Write JS script to /tmp on host, then docker cp into container and run
js = r"""const {Pool} = require('pg');
const p = new Pool({
  host: process.env.DB_HOST,
  port: parseInt(process.env.DB_PORT || '5432'),
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME,
  ssl: { rejectUnauthorized: false }
});
p.query("SELECT column_name FROM information_schema.columns WHERE table_name='api_keys'")
.then(r => {
  console.log('api_keys columns:', r.rows.map(c=>c.column_name).join(', '));
  return p.query("SELECT id, name, app_name FROM api_keys WHERE LOWER(name)='default key'");
}).then(r => {
  console.log('Found rows:', JSON.stringify(r.rows));
  if (!r.rows.length) { console.log('No Default Key found'); p.end(); return; }
  return p.query(
    "UPDATE api_keys SET app_name=$1 WHERE LOWER(name)=$2 AND (app_name IS NULL OR app_name='')",
    ['CUPOL VPN', 'default key']
  ).then(u => {
    console.log('Updated:', u.rowCount, 'rows');
    return p.query("SELECT id, name, app_name FROM api_keys WHERE LOWER(name)='default key'");
  }).then(v => { console.log('After update:', JSON.stringify(v.rows)); p.end(); });
}).catch(e => { console.error('ERROR:', e.message); p.end(); });
"""

# Write to host /tmp
sftp = ssh.open_sftp()
with sftp.open('/tmp/fix_keys.js', 'w') as f:
    f.write(js)
sftp.close()

# Copy into container and run
def run(cmd):
    _, o, e = ssh.exec_command(cmd)
    out = o.read().decode().strip()
    err = e.read().decode().strip()
    if out: print("OUT:", out)
    if err: print("ERR:", err)
    return out, err

container = 'tokenpay-id-api'
# Show all DB-related env vars
run(f"docker exec {container} env | grep -iE 'db|pg|postgres|sql|database'")
# Also check the config file
run(f"docker exec {container} cat /app/config.js 2>/dev/null | head -40 || cat /app/src/config.js 2>/dev/null | head -40 || echo 'no config.js'")
run(f"docker exec {container} cat /app/.env 2>/dev/null | grep -iE 'db|pg|postgres' || echo 'no .env'")
# Copy and run fix
run(f"docker cp /tmp/fix_keys.js {container}:/app/fix_keys.js")
run(f"docker exec -w /app {container} node /app/fix_keys.js")

ssh.close()
print("Done.")

#!/bin/bash
# Timeweb Cloud API Deployment Script
# Documentation: https://timeweb.cloud/api-docs

API_KEY="eyJhbGciOiJSUzUxMiIsInR5cCI6IkpXVCIsImtpZCI6IjFrYnhacFJNQGJSI0tSbE1xS1lqIn0.eyJ1c2VyIjoibXUwNjQxODkiLCJ0eXBlIjoiYXBpX2tleSIsImFwaV9rZXlfaWQiOiIyM2Y4NzU5MC03OGUyLTQwYTAtYTJlMS02NTQ0NjBlNTgwNzIiLCJpYXQiOjE3NzQyODY4MDh9.gepkkJoKTSQsGXay5OOmjv7in1YdfWukY7_ZIhmwy816ZJtv3i_CixD_u4S_fjTM_jj2mow3LW3zkoEskiCOjTbxC2aPHgSlnnm1Kx2WlKCON7pCqtF2DRP1RLUkVureSUmqInBifH7gpeJUiYVa3gyY4fvyKmKzdIsLyp63CpFVOi_KuxRtHszujX2ZWpajo8PyXaLC8hv5R062SXfSKRae100Cb5t7O6eX49Bj8ClidsH_mQAS69XJ4DoBU5zMYTWsVZWTX_pHjOzOYWiBShQjPO1icKxZmQx_w8lqHSZucELpQ9v8552Gs3yudlWbcfhgpt0J0oHDDMcc-xjRDkKWuLZQjfMcgw0ooPAGENAxmbYcR5S_WFR3BNT3M2g-fOi7aSSjX5ufAjz7vj3AOsV9Re-QAC6NC01ZQGS50KrqEKPT2D0K6TYL9VBDcpgbiC1WNhNCE5ALdL72j2vhXH4uo63aflbKcIVHD2h7pN7gQO2xVF63tFyzdUGb9a3K"

SERVER_IP="5.23.54.205"
DB_IP="5.23.55.152"
SERVER_PASS="vE^6t-zFS3dpNT"
DB_PASS="93JJFQLAYC=Uo)"

CF_ZONE_ID="210a25c077c2bfdc43a853762ccb358d"
CF_ACCOUNT_ID="7b3dcd325574c3ca17e376b49d2875a9"
CF_API_KEY="5a4a5eddcb5882e068e0c407b670df0ef65ac"

API_BASE="https://api.timeweb.cloud"

echo "=== Timeweb Cloud Deployment ==="
echo ""

# Function to make API calls
tw_api() {
    curl -s -H "Authorization: Bearer $API_KEY" \
         -H "Content-Type: application/json" \
         "$@"
}

# 1. Get server info
echo "[1] Getting server information..."
SERVER_RESPONSE=$(tw_api "$API_BASE/api/v1/servers")
echo "Servers: $(echo $SERVER_RESPONSE | grep -o '"ip":"[^"]*"' | head -1)"

# 2. Upload files via SFTP (Timeweb uses standard SFTP)
echo ""
echo "[2] Uploading frontend files via SFTP..."
echo "   Connecting to $SERVER_IP..."

# Create temp archive
cd frontend
tar -czf ../tokenpay-deploy.tar.gz .
cd ..

# Upload using expect or sshpass if available, otherwise manual
echo "   Files ready for upload: tokenpay-deploy.tar.gz"
echo ""
echo "   SFTP Command:"
echo "   sftp root@$SERVER_IP"
echo "   Password: $SERVER_PASS"
echo "   put tokenpay-deploy.tar.gz /var/www/"
echo ""

# 3. Extract and deploy on server
echo "[3] Deployment commands for server:"
echo ""
cat << 'REMOTE_COMMANDS'
# On server (SSH as root):
cd /var/www/tokenpay
tar -xzf ../tokenpay-deploy.tar.gz

# Sync to subdomains
cp -r /var/www/tokenpay/* /var/www/auth/
cp -r /var/www/tokenpay/* /var/www/id/

# Set index pages
ln -sf /var/www/auth/login.html /var/www/auth/index.html
ln -sf /var/www/id/dashboard.html /var/www/id/index.html

# Fix permissions
chown -R www-data:www-data /var/www/tokenpay /var/www/auth /var/www/id
chmod -R 644 /var/www/tokenpay/* /var/www/auth/* /var/www/id/*
find /var/www -type d -exec chmod 755 {} \;

# Restart nginx if needed
systemctl reload nginx
REMOTE_COMMANDS

echo ""
echo "=== Deployment Package Ready ==="
echo ""
echo "Next steps:"
echo "1. Upload tokenpay-deploy.tar.gz to server"
echo "2. Extract to /var/www/tokenpay/"
echo "3. Run sync commands above"
echo ""
echo "Or use SSH directly:"
echo "ssh root@$SERVER_IP"
echo ""

# Cleanup
rm -f tokenpay-deploy.tar.gz

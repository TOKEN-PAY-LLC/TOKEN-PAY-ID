#!/bin/bash
# TokenPay Deployment Script for Linux/Mac

SERVER_IP="5.23.54.205"
SSH_USER="root"
WWW_ROOT="/var/www"

echo "=== TokenPay Deployment ==="
echo ""

# Main site
echo "[1/3] Deploying to tokenpay.space..."
scp -r frontend/* ${SSH_USER}@${SERVER_IP}:${WWW_ROOT}/tokenpay/

# Auth subdomain
echo "[2/3] Syncing to auth.tokenpay.space..."
ssh ${SSH_USER}@${SERVER_IP} "cp -r ${WWW_ROOT}/tokenpay/* ${WWW_ROOT}/auth/ 2>/dev/null; rm -f ${WWW_ROOT}/auth/index.html; ln -s ${WWW_ROOT}/auth/login.html ${WWW_ROOT}/auth/index.html"

# ID subdomain (dashboard as index)
echo "[3/3] Syncing to id.tokenpay.space..."
ssh ${SSH_USER}@${SERVER_IP} "cp -r ${WWW_ROOT}/tokenpay/* ${WWW_ROOT}/id/ 2>/dev/null; rm -f ${WWW_ROOT}/id/index.html; ln -s ${WWW_ROOT}/id/dashboard.html ${WWW_ROOT}/id/index.html"

# Fix permissions
echo "[*] Setting permissions..."
ssh ${SSH_USER}@${SERVER_IP} "chown -R www-data:www-data ${WWW_ROOT}/tokenpay ${WWW_ROOT}/auth ${WWW_ROOT}/id 2>/dev/null || true"

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "URLs:"
echo "  https://tokenpay.space"
echo "  https://auth.tokenpay.space"
echo "  https://id.tokenpay.space"
echo ""

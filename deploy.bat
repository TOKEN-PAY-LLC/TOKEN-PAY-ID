@echo off
echo === TokenPay Deployment Script ===
echo.

set SERVER_IP=5.23.54.205
set SSH_USER=root

echo [1/4] Deploying to tokenpay.space (main)...
scp -r index.html styles.css script.js theme-init.js captcha.js dashboard.html login.html register.html docs.html terms.html privacy.html admin.html enterprise.html password-reset.html verify-email.html favicon.ico *.png *.svg %SSH_USER%@%SERVER_IP%:/var/www/tokenpay/

echo [2/4] Syncing to auth.tokenpay.space...
ssh %SSH_USER%@%SERVER_IP% "cp -r /var/www/tokenpay/* /var/www/auth/ && ln -sf /var/www/auth/login.html /var/www/auth/index.html"

echo [3/4] Syncing to id.tokenpay.space...
ssh %SSH_USER%@%SERVER_IP% "cp -r /var/www/tokenpay/* /var/www/id/ && ln -sf /var/www/id/dashboard.html /var/www/id/index.html"

echo [4/4] Setting permissions...
ssh %SSH_USER%@%SERVER_IP% "chown -R www-data:www-data /var/www/tokenpay /var/www/auth /var/www/id && chmod -R 644 /var/www/tokenpay/* /var/www/auth/* /var/www/id/*"

echo.
echo === Deployment Complete ===
echo.
echo URLs:
echo   https://tokenpay.space
echo   https://auth.tokenpay.space
echo   https://id.tokenpay.space
echo.
pause

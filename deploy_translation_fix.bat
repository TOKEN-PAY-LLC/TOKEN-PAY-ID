@echo off
echo Deploying translation and TPID button fix...
scp -o StrictHostKeyChecking=no frontend\index.html frontend\theme-init.js frontend\script.js frontend\styles.css root@5.23.54.205:/var/www/tokenpay/
echo Syncing to subdomains...
ssh -o StrictHostKeyChecking=no root@5.23.54.205 "cp /var/www/tokenpay/index.html /var/www/tokenpay/theme-init.js /var/www/tokenpay/script.js /var/www/tokenpay/styles.css /var/www/auth/ && cp /var/www/tokenpay/index.html /var/www/tokenpay/theme-init.js /var/www/tokenpay/script.js /var/www/tokenpay/styles.css /var/www/id/ && chown -R www-data:www-data /var/www/tokenpay /var/www/auth /var/www/id && systemctl reload nginx && echo DONE"
echo Deployment complete!
pause

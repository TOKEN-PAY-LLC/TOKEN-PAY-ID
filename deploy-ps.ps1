# PowerShell Deployment Script with Password Authentication
$ErrorActionPreference = "Stop"

$SERVER_IP = "5.23.54.205"
$SSH_USER = "root"
$PASSWORD = "vE^6t-zFS3dpNT"
$DEPLOY_PATH = "c:\Users\user\Desktop\TokenPay-Website"

Write-Host "=== TokenPay Deployment ===" -ForegroundColor Cyan
Write-Host ""

# Load Posh-SSH module or install if not present
try {
    Import-Module Posh-SSH -ErrorAction Stop
    Write-Host "Posh-SSH module loaded" -ForegroundColor Green
} catch {
    Write-Host "Installing Posh-SSH module..." -ForegroundColor Yellow
    Install-Module Posh-SSH -Force -Scope CurrentUser
    Import-Module Posh-SSH
}

# Create SSH session
Write-Host "[1/4] Connecting to server $SERVER_IP..." -ForegroundColor Cyan
$SecurePassword = ConvertTo-SecureString $PASSWORD -AsPlainText -Force
$Credential = New-Object System.Management.Automation.PSCredential($SSH_USER, $SecurePassword)

$Session = New-SSHSession -ComputerName $SERVER_IP -Credential $Credential -AcceptKey
Write-Host "Connected!" -ForegroundColor Green

# Create archive
Write-Host "[2/4] Creating deployment archive..." -ForegroundColor Cyan
Set-Location $DEPLOY_PATH
if (Test-Path "tokenpay-deploy.tar.gz") { Remove-Item "tokenpay-deploy.tar.gz" }
Compress-Archive -Path "frontend\*" -DestinationPath "tokenpay-deploy.zip" -Force
Write-Host "Archive created" -ForegroundColor Green

# Upload via SFTP
Write-Host "[3/4] Uploading files via SFTP..." -ForegroundColor Cyan
Set-SCPFile -ComputerName $SERVER_IP -Credential $Credential `
    -LocalFile "$DEPLOY_PATH\tokenpay-deploy.zip" `
    -RemotePath "/var/www/" `
    -AcceptKey
Write-Host "Upload complete" -ForegroundColor Green

# Execute deployment commands
Write-Host "[4/4] Deploying on server..." -ForegroundColor Cyan
$Commands = @"
cd /var/www
unzip -o tokenpay-deploy.zip -d tokenpay/
rm -f tokenpay-deploy.zip

# Sync to subdomains
cp -r /var/www/tokenpay/* /var/www/auth/
cp -r /var/www/tokenpay/* /var/www/id/

# Set index pages
rm -f /var/www/auth/index.html
ln -sf /var/www/auth/login.html /var/www/auth/index.html
rm -f /var/www/id/index.html
ln -sf /var/www/id/dashboard.html /var/www/id/index.html

# Fix permissions
chown -R www-data:www-data /var/www/tokenpay /var/www/auth /var/www/id
chmod -R 644 /var/www/tokenpay/* /var/www/auth/* /var/www/id/*
find /var/www -type d -exec chmod 755 {} \;

# Reload nginx
systemctl reload nginx

echo "Deployment complete!"
"@

$result = Invoke-SSHCommand -SSHSession $Session -Command $Commands
Write-Host $result.Output -ForegroundColor Gray

# Close session
Remove-SSHSession -SSHSession $Session
Write-Host ""
Write-Host "=== Deployment Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Sites deployed:" -ForegroundColor Cyan
Write-Host "  https://tokenpay.space" -ForegroundColor White
Write-Host "  https://auth.tokenpay.space" -ForegroundColor White
Write-Host "  https://id.tokenpay.space" -ForegroundColor White
Write-Host ""

pause

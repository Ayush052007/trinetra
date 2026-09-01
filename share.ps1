# ===========================================================================
# TRINETRA - share on your local network
#
# Binds to every interface so other devices on the same Wi-Fi can reach the
# platform, and prints the URL to hand out.
#
#   .\share.ps1
#
# Windows Firewall will likely prompt the first time - allow it on Private
# networks. If you get no prompt and others cannot connect, run this once
# from an ADMIN PowerShell:
#
#   New-NetFirewallRule -DisplayName "TRINETRA 8000" -Direction Inbound `
#       -LocalPort 8000 -Protocol TCP -Action Allow -Profile Private
# ===========================================================================

$port = 8000

$ip = (Get-NetIPAddress -AddressFamily IPv4 |
       Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
       Select-Object -First 1).IPAddress

Write-Host ""
Write-Host "  TRINETRA is starting..." -ForegroundColor Cyan
Write-Host ""
Write-Host "  On this machine :  http://localhost:$port"
if ($ip) {
    Write-Host "  On this network :  http://$ip`:$port" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Share the green URL with anyone on the same Wi-Fi."
} else {
    Write-Host "  No network adapter found - localhost only." -ForegroundColor Yellow
}
Write-Host ""
Write-Host "  Sign-in credentials are in CREDENTIALS.md"
Write-Host "  Press Ctrl+C to stop." -ForegroundColor DarkGray
Write-Host ""

$env:PYTHONPATH = "backend;database;ai;graph"
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port $port

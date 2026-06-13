# Проверка HTTP API 1С для bot-service
param(
    [string]$BaseUrl = "http://localhost:8081/unf",
    [string]$User = $env:ONEC_USERNAME,
    [string]$Password = $env:ONEC_PASSWORD
)

if (-not $User) { $User = "BotAPI" }
if (-not $Password) {
    Write-Host "Задайте ONEC_PASSWORD в окружении или параметр -Password" -ForegroundColor Yellow
}

$pair = "${User}:${Password}"
$b64 = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($pair))
$headers = @{ Authorization = "Basic $b64" }

Write-Host "=== ping ===" -ForegroundColor Cyan
try {
    $r = Invoke-WebRequest "$BaseUrl/hs/nomenclature_bot/ping" -Headers $headers -UseBasicParsing -TimeoutSec 30
    Write-Host "OK $($r.StatusCode): $($r.Content)" -ForegroundColor Green
} catch {
    Write-Host "FAIL: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n=== search GET (legacy q) ===" -ForegroundColor Cyan
try {
    $r = Invoke-WebRequest "$BaseUrl/hs/nomenclature_bot/v1/search?q=1&limit=2" -Headers $headers -UseBasicParsing -TimeoutSec 60
    Write-Host "OK $($r.StatusCode)" -ForegroundColor Green
    Write-Host $r.Content
} catch {
    Write-Host "FAIL: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n=== search POST (smart) ===" -ForegroundColor Cyan
try {
    $body = @{
        barcode = ""
        article = ""
        tokens  = @("1")
        limit   = 2
    } | ConvertTo-Json -Compress

    $r = Invoke-WebRequest `
        "$BaseUrl/hs/nomenclature_bot/v1/search" `
        -Method POST `
        -Headers $headers `
        -ContentType "application/json; charset=utf-8" `
        -Body ([System.Text.Encoding]::UTF8.GetBytes($body)) `
        -UseBasicParsing `
        -TimeoutSec 60

    Write-Host "OK $($r.StatusCode)" -ForegroundColor Green
    Write-Host $r.Content
} catch {
    Write-Host "FAIL: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n=== auth verify POST ===" -ForegroundColor Cyan
try {
    $body = @{ phone = "+79000000000" } | ConvertTo-Json -Compress
    $r = Invoke-WebRequest `
        "$BaseUrl/hs/nomenclature_bot/v1/auth/verify" `
        -Method POST `
        -Headers $headers `
        -ContentType "application/json; charset=utf-8" `
        -Body ([System.Text.Encoding]::UTF8.GetBytes($body)) `
        -UseBasicParsing `
        -TimeoutSec 60
    Write-Host "OK $($r.StatusCode)" -ForegroundColor Green
    Write-Host $r.Content
} catch {
    Write-Host "FAIL: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        Write-Host $reader.ReadToEnd()
    }
}

# ============================================================
# 课程答疑平台 - 一键启动
# 用法: powershell -ExecutionPolicy Bypass -File .\start-all.ps1
# 停止: powershell -ExecutionPolicy Bypass -File .\stop-all.ps1
# ============================================================

$root = $PSScriptRoot
$ErrorActionPreference = 'SilentlyContinue'

# ---- 1. Clean ports 8000 / 8001 ----
$killed = @()
foreach ($port in 8000, 8001) {
    foreach ($c in (Get-NetTCPConnection -LocalPort $port -State Listen)) {
        $proc = Get-Process -Id $c.OwningProcess
        if ($proc -and $killed -notcontains $proc.Id) {
            Stop-Process -Id $proc.Id -Force
            $killed += $proc.Id
            Write-Host ("[clean] port {0} freed (PID {1})" -f $port, $proc.Id) -ForegroundColor Yellow
        }
    }
}

# ---- 2. Backend services ----
Write-Host ""
Write-Host "[start] backend services..." -ForegroundColor Cyan
Start-Process -FilePath "python" -ArgumentList "-m", "docs_service" -WorkingDirectory $root
Write-Host "        docs_service -> http://127.0.0.1:8000"
Start-Process -FilePath "python" -ArgumentList "-m", "rag_service" -WorkingDirectory $root
Write-Host "        rag_service  -> http://127.0.0.1:8001 (vector store warmup ~30s)"

# ---- 3. Frontend Vite (5173) ----
$webDir = Join-Path $root 'web'
if (Get-NetTCPConnection -LocalPort 5173 -State Listen) {
    Write-Host ""
    Write-Host "[skip]  frontend 5173 already running" -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "[start] frontend..." -ForegroundColor Cyan
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "npm run dev" -WorkingDirectory $webDir
    Write-Host "        vite       -> http://127.0.0.1:5173"
}

# ---- 4. Wait until ready, then open browser ----
Write-Host ""
Write-Host "[wait]  waiting for services..." -ForegroundColor Cyan
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 2
    $docsOk = (Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/health' -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200
    $ragOk  = (Invoke-WebRequest -Uri 'http://127.0.0.1:8001/api/health' -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200
    $webOk  = (Invoke-WebRequest -Uri 'http://127.0.0.1:5173' -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200
    if ($docsOk -and $ragOk -and $webOk) { $ready = $true; break }
    Write-Host ("        ... docs:{0} rag:{1} web:{2}" -f $docsOk, $ragOk, $webOk)
}

if ($ready) {
    Write-Host ""
    Write-Host "[ok]    all services ready, opening browser" -ForegroundColor Green
    Start-Process "http://127.0.0.1:5173"
} else {
    Write-Host ""
    Write-Host "[warn]  some services not ready within 120s; check the spawned windows" -ForegroundColor Red
}

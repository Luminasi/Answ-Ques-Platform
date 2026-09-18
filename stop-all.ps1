# ============================================================
# 课程答疑平台 - 一键停止
# 停止占用 8000 / 8001 / 5173 端口的全部进程
# ============================================================

$ErrorActionPreference = 'SilentlyContinue'
$killed = @()

foreach ($port in 8000, 8001, 5173) {
    foreach ($c in (Get-NetTCPConnection -LocalPort $port -State Listen)) {
        $proc = Get-Process -Id $c.OwningProcess
        if ($proc -and $killed -notcontains $proc.Id) {
            Stop-Process -Id $proc.Id -Force
            $killed += $proc.Id
            Write-Host ("[stop] port {0} (PID {1}, {2})" -f $port, $proc.Id, $proc.ProcessName) -ForegroundColor Yellow
        }
    }
}

# Vite dev server: extra sweep for node processes under this project
Get-CimInstance Win32_Process -Filter "Name='node.exe'" | Where-Object {
    $_.CommandLine -match 'answer-question-APP' -and $_.CommandLine -match 'vite'
} | ForEach-Object {
    if ($killed -notcontains $_.ProcessId) {
        Stop-Process -Id $_.ProcessId -Force
        Write-Host ("[stop] vite node (PID {0})" -f $_.ProcessId) -ForegroundColor Yellow
        $killed += $_.ProcessId
    }
}

if (-not $killed) {
    Write-Host "[info] no services running" -ForegroundColor Gray
} else {
    Write-Host ""
    Write-Host "[ok] all services stopped" -ForegroundColor Green
}

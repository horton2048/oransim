# Launch Oransim (backend api-mode + frontend) on this machine.
# Usage:  powershell -ExecutionPolicy Bypass -File .\run-oransim.ps1
# Reads .env (simple KEY=VALUE lines), exports to process env, starts both servers.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

# --- load .env into process env ---
Get-Content (Join-Path $root ".env") | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
        $i = $line.IndexOf("=")
        $k = $line.Substring(0, $i).Trim()
        $v = $line.Substring($i + 1).Trim()
        Set-Item -Path "Env:$k" -Value $v
    }
}
$env:PYTHONIOENCODING = "utf-8"

$py = Join-Path $root ".venv\Scripts\python.exe"

# --- stop anything already on the ports ---
foreach ($port in 8001, 8090) {
    $c = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($c) { $c.OwningProcess | Select-Object -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue } }
}

# Bind host: 0.0.0.0 exposes both servers on the LAN so colleagues can reach
# http://<this-machine-LAN-IP>:8090. Set OSIM_BIND=127.0.0.1 to go local-only.
$bind = if ($env:OSIM_BIND) { $env:OSIM_BIND } else { "0.0.0.0" }

# --- backend ---
Start-Process -FilePath $py `
    -ArgumentList "-m", "uvicorn", "oransim.api:app", "--host", $bind, "--port", $env:PORT `
    -RedirectStandardOutput (Join-Path $root ".run-backend.log") `
    -RedirectStandardError  (Join-Path $root ".run-backend.err.log") `
    -WindowStyle Hidden

# --- frontend ---
Start-Process -FilePath $py `
    -ArgumentList "-m", "http.server", "8090", "--bind", $bind, "--directory", "frontend" `
    -RedirectStandardOutput (Join-Path $root ".run-frontend.log") `
    -RedirectStandardError  (Join-Path $root ".run-frontend.err.log") `
    -WindowStyle Hidden

Start-Sleep -Seconds 6
Write-Host "Backend : http://localhost:$($env:PORT)   (LLM_MODE=$($env:LLM_MODE), model=$($env:LLM_MODEL))"
Write-Host "Frontend: http://localhost:8090"
try {
    $h = Invoke-RestMethod "http://localhost:$($env:PORT)/api/health" -TimeoutSec 10
    Write-Host "Health  : $($h.status) | llm.mode=$($h.llm.mode) key_set=$($h.llm.api_key_set) | $($h.population) agents / $($h.souls) souls"
} catch {
    Write-Host "Health check failed — see .run-backend.err.log"
}

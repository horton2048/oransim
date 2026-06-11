# Acceptance gate -- run before merging each milestone in the unattended loop.
# ASCII-only on purpose: Windows PowerShell 5.1 reads .ps1 as the system
# codepage (GBK), so non-ASCII here would mojibake and break parsing.
#
# Usage:
#   pwsh scripts/accept.ps1            # full mock suite (REG-1/2/3 + accumulated AT)
#   pwsh scripts/accept.ps1 -K at_m0   # only one milestone's cases (pytest -k filter)
#   pwsh scripts/accept.ps1 -Reg4      # also assert engine layer has no import oransim.spec (REG-4, from M1)
#
# Exit code: 0 = all green, mergeable; non-zero = red, do NOT merge.
# Iron rules: LLM_MODE=mock forces zero network egress; golden snapshot byte-stable.

param(
    [string]$K = "",
    [switch]$Reg4
)

$ErrorActionPreference = "Stop"
$env:LLM_MODE = "mock"          # REG-3: force mock, no network egress
$env:PYTHONHASHSEED = "0"       # deterministic hash() for cross-session snapshot stability
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

# Prefer project venv python (system python has no pytest)
$py = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

Write-Host "== acceptance gate (LLM_MODE=mock) ==" -ForegroundColor Cyan

# REG-4 (from M1): engine layer must not import the spec/ package. grep verifies.
if ($Reg4) {
    Write-Host "-- REG-4: engine dependency-direction check --" -ForegroundColor Cyan
    $engineDirs = @(
        "backend/oransim/data", "backend/oransim/config", "backend/oransim/agents",
        "backend/oransim/diffusion", "backend/oransim/causal", "backend/oransim/sandbox"
    )
    $hits = @()
    foreach ($d in $engineDirs) {
        if (Test-Path $d) {
            $hits += Select-String -Path "$d/*.py" -Pattern 'import\s+oransim\.spec|from\s+oransim\.spec' -ErrorAction SilentlyContinue
        }
    }
    if ($hits.Count -gt 0) {
        Write-Host "REG-4 FAILED: engine layer imports oransim.spec:" -ForegroundColor Red
        $hits | ForEach-Object { Write-Host ("  {0}:{1}: {2}" -f $_.Path, $_.LineNumber, $_.Line.Trim()) -ForegroundColor Red }
        exit 1
    }
    Write-Host "REG-4 OK." -ForegroundColor Green
}

# Main suite
$pytestArgs = @("tests/")
if ($K -ne "") { $pytestArgs += @("-k", $K) }

Write-Host ("-- pytest {0} --" -f ($pytestArgs -join ' ')) -ForegroundColor Cyan
& $py -m pytest @pytestArgs
$code = $LASTEXITCODE

if ($code -eq 0) {
    Write-Host "== gate ALL GREEN, mergeable. ==" -ForegroundColor Green
} else {
    Write-Host ("== gate RED (exit {0}), do NOT merge. ==" -f $code) -ForegroundColor Red
}
exit $code

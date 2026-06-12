# run-live.ps1 — 跑 @live_llm 用例 (AT-M2-02 + M8 live 复跑) against a real LLM.
#
# 从仓库根 .env 加载真实 LLM 配置 (LLM_MODE/LLM_BASE_URL/LLM_API_KEY/LLM_MODEL),
# 然后运行 skip-by-default 的 live 用例。key 只进环境变量与 Authorization 头,
# 全程不回显。.env 已 gitignore。
#
# 用法:  pwsh scripts/run-live.ps1
# 前置:  .env 含可用的 OpenAI-compatible LLM 配置 (本机已配 MiniMax-Text-01)。
#
# 断言: live 黄金集品类映射准确率 >= 85% + B2B 反例全部硬拒绝 (与 mock 分别记录)。

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $repo ".env"

if (-not (Test-Path $envFile)) {
    Write-Host "缺少 .env — 无法跑 live 用例。请在仓库根放 .env (LLM_MODE=api 等)。" -ForegroundColor Red
    exit 1
}

# 加载 .env (值不回显)
Get-Content $envFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith('#') -and $line.Contains('=')) {
        $i = $line.IndexOf('=')
        $k = $line.Substring(0, $i).Trim()
        $v = $line.Substring($i + 1).Trim().Trim('"').Trim("'")
        [Environment]::SetEnvironmentVariable($k, $v, 'Process')
    }
}
$env:PYTHONHASHSEED = "0"

# 仅打印非密配置, 确认连的是哪个供应商/模型
Write-Host ("== live LLM: MODE={0} PROVIDER={1} MODEL={2} BASE_URL={3} KEY_SET={4} ==" -f `
    $env:LLM_MODE, $env:LLM_PROVIDER, $env:LLM_MODEL, $env:LLM_BASE_URL, [bool]$env:LLM_API_KEY) `
    -ForegroundColor Cyan

Set-Location $repo
$py = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

& $py -m pytest tests/ -p no:cacheprovider -k "m2_02 or m8_live" --run-live -s
exit $LASTEXITCODE

param(
  [string]$CdpUrl = "",
  [string]$Prompt = "Please reply exactly: doubao smoke test success",
  [string]$Screenshot = "",
  [string]$TextOut = "",
  [int]$TimeoutMs = 60000
)

$ErrorActionPreference = "Stop"

if (-not $CdpUrl) {
  $CdpUrl = if ($env:DOUBAO_CDP_URL) { $env:DOUBAO_CDP_URL } else { "http://127.0.0.1:9222" }
}

$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) { throw "node.exe was not found on PATH." }

$npm = Get-Command npm -ErrorAction SilentlyContinue
if (-not $npm) { throw "npm was not found on PATH." }

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$runtimeRoot = Join-Path $scriptRoot ".runtime\playwright"
$nodeModules = Join-Path $runtimeRoot "node_modules"
$packageDir = Join-Path $nodeModules "playwright"

if (-not (Test-Path $packageDir)) {
  New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
  & $npm.Source @("install", "--prefix", $runtimeRoot, "--no-audit", "--no-fund", "--no-save", "playwright")
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$oldNodePath = $env:NODE_PATH
$env:NODE_PATH = if ($oldNodePath) { "$nodeModules;$oldNodePath" } else { $nodeModules }

$nodeArgs = @(
  (Join-Path $scriptRoot "doubao_chrome_smoke.js"),
  "--cdp-url", $CdpUrl,
  "--prompt", $Prompt,
  "--timeout-ms", "$TimeoutMs"
)

if ($Screenshot) { $nodeArgs += @("--screenshot", $Screenshot) }
if ($TextOut) { $nodeArgs += @("--text-out", $TextOut) }

try {
  & $node.Source @nodeArgs
  exit $LASTEXITCODE
} finally {
  $env:NODE_PATH = $oldNodePath
}

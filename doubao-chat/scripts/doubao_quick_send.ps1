param(
  [Parameter(Mandatory = $true)]
  [string]$Prompt,
  [string]$CdpUrl = "",
  [int]$WaitMs = 10000,
  [int]$TimeoutMs = 30000,
  [string]$Screenshot = "",
  [string]$ReplyOut = "",
  [string]$BodyOut = "",
  [string[]]$ImagePath = @(),
  [int]$CooldownMs = 12000,
  [string]$Url = "https://www.doubao.com/chat/",
  [switch]$LaunchChrome,
  [switch]$ReuseCurrentChat
)

$ErrorActionPreference = "Stop"

if (-not $CdpUrl) {
  $CdpUrl = if ($env:DOUBAO_CDP_URL) {
    $env:DOUBAO_CDP_URL
  } elseif ($env:CHROME_DIDY_CDP_URL) {
    $env:CHROME_DIDY_CDP_URL
  } else {
    "http://127.0.0.1:9222"
  }
}

function Get-DebugPort([string]$Url) {
  $uri = [Uri]$Url
  if ($uri.Port -le 0) { return 9222 }
  return $uri.Port
}

function Test-Cdp([string]$Url) {
  try {
    $null = Invoke-RestMethod -Uri "$Url/json/version" -TimeoutSec 2
    return $true
  } catch {
    return $false
  }
}

function Find-Chrome {
  $cmd = Get-Command chrome.exe -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }

  $candidates = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
  )

  foreach ($candidate in $candidates) {
    if ($candidate -and (Test-Path $candidate)) { return $candidate }
  }

  return ""
}

if (-not (Test-Cdp $CdpUrl)) {
  if (-not $LaunchChrome) {
    throw "Chrome DevTools endpoint is not reachable at $CdpUrl. Start Chrome with remote debugging, set DOUBAO_CDP_URL, or rerun with -LaunchChrome."
  }

  $chrome = Find-Chrome
  if (-not $chrome) { throw "chrome.exe was not found. Install Chrome or put chrome.exe on PATH." }

  $scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
  $profileDir = Join-Path $scriptRoot ".runtime\chrome-profile"
  New-Item -ItemType Directory -Force -Path $profileDir | Out-Null

  $port = Get-DebugPort $CdpUrl
  Start-Process -FilePath $chrome -ArgumentList @(
    "--remote-debugging-port=$port",
    "--user-data-dir=$profileDir",
    "--no-first-run",
    "--disable-background-mode",
    $Url
  ) | Out-Null

  $deadline = (Get-Date).AddSeconds(15)
  while ((Get-Date) -lt $deadline) {
    if (Test-Cdp $CdpUrl) { break }
    Start-Sleep -Milliseconds 500
  }

  if (-not (Test-Cdp $CdpUrl)) {
    throw "Started Chrome, but DevTools endpoint did not become reachable at $CdpUrl."
  }
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
  (Join-Path $scriptRoot "doubao_quick_send.js"),
  "--cdp-url", $CdpUrl,
  "--url", $Url,
  "--prompt", $Prompt,
  "--wait-ms", "$WaitMs",
  "--timeout-ms", "$TimeoutMs",
  "--cooldown-ms", "$CooldownMs"
)

if ($Screenshot) { $nodeArgs += @("--screenshot", $Screenshot) }
if ($ReplyOut) { $nodeArgs += @("--reply-out", $ReplyOut) }
if ($BodyOut) { $nodeArgs += @("--body-out", $BodyOut) }
foreach ($image in $ImagePath) {
  if ($image) { $nodeArgs += @("--image", $image) }
}
if ($ReuseCurrentChat) { $nodeArgs += @("--reuse-current-chat") }

try {
  & $node.Source @nodeArgs
  exit $LASTEXITCODE
} finally {
  $env:NODE_PATH = $oldNodePath
}

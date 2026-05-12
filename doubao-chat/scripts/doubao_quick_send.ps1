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
  [int]$CooldownMs = 30000,
  [string]$Url = "https://www.doubao.com/chat/",
  [string]$ChromePath = "",
  [switch]$LaunchChrome,
  [switch]$UseDefaultChromeProfile,
  [switch]$ReuseCurrentChat,
  [switch]$NewChat,
  [switch]$AllowFastSend
)

$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$statePath = Join-Path $scriptRoot ".runtime\doubao-state.json"

function Read-StateCdpUrl([string]$Path) {
  if (-not (Test-Path $Path)) { return "" }
  try {
    $state = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    if ($state.lastGoodCdpUrl) { return [string]$state.lastGoodCdpUrl }
  } catch {
    return ""
  }
  return ""
}

function Read-StateLastUrl([string]$Path) {
  if (-not (Test-Path $Path)) { return "" }
  try {
    $state = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    if ($state.lastUrl -and ([string]$state.lastUrl) -match '^https://www\.doubao\.com/chat/') {
      return [string]$state.lastUrl
    }
  } catch {
    return ""
  }
  return ""
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

if (-not $CdpUrl) {
  $stateCdpUrl = Read-StateCdpUrl $statePath
  $candidateCdpUrls = @(
    $stateCdpUrl,
    $env:DOUBAO_CDP_URL,
    $env:CHROME_DIDY_CDP_URL,
    "http://127.0.0.1:9222"
  )
  foreach ($candidateCdpUrl in $candidateCdpUrls) {
    if ($candidateCdpUrl -and (Test-Cdp $candidateCdpUrl)) {
      $CdpUrl = $candidateCdpUrl
      break
    }
  }
  if (-not $CdpUrl) {
    $CdpUrl = "http://127.0.0.1:9222"
  }
}

if (-not $PSBoundParameters.ContainsKey("Url") -and -not $NewChat) {
  $stateLastUrl = Read-StateLastUrl $statePath
  if ($stateLastUrl) {
    $Url = $stateLastUrl
  }
}

function Find-Chrome([string]$Explicit) {
  if ($Explicit -and (Test-Path $Explicit)) { return $Explicit }

  $cmd = Get-Command chrome.exe -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }

  $registryChrome = @()
  $registryKeys = @(
    "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"
  )
  foreach ($key in $registryKeys) {
    if (Test-Path $key) {
      $value = (Get-Item $key).GetValue("")
      if ($value) { $registryChrome += $value }
    }
  }

  $candidates = @(
    $env:DOUBAO_CHROME_PATH,
    $env:CHROME_DIDY_CHROME_PATH,
    $env:CHROME_PATH
  ) + $registryChrome + @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
    "E:\MorenAnzhuangLujing\Chrome\Chrome\Application\chrome.exe"
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

  $chrome = Find-Chrome $ChromePath
  if (-not $chrome) { throw "chrome.exe was not found. Install Chrome or put chrome.exe on PATH." }

  $port = Get-DebugPort $CdpUrl
  $chromeArgs = @(
    "--remote-debugging-port=$port",
    "--no-first-run",
    "--disable-background-mode",
    $Url
  )

  if (-not $UseDefaultChromeProfile) {
    $profileDir = Join-Path $scriptRoot ".runtime\chrome-profile"
    New-Item -ItemType Directory -Force -Path $profileDir | Out-Null
    $chromeArgs = @(
      "--remote-debugging-port=$port",
      "--user-data-dir=$profileDir",
      "--no-first-run",
      "--disable-background-mode",
      $Url
    )
  }

  Start-Process -FilePath $chrome -ArgumentList $chromeArgs | Out-Null

  $deadline = (Get-Date).AddSeconds(15)
  while ((Get-Date) -lt $deadline) {
    if (Test-Cdp $CdpUrl) { break }
    Start-Sleep -Milliseconds 500
  }

  if (-not (Test-Cdp $CdpUrl)) {
    if ($UseDefaultChromeProfile) {
      throw "Started Chrome with the default profile, but DevTools did not become reachable at $CdpUrl. Chrome 136+ does not allow remote debugging on the default user data directory; use the persistent controlled profile from -LaunchChrome and log into Doubao there once."
    }
    throw "Started Chrome, but DevTools endpoint did not become reachable at $CdpUrl."
  }
}

$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) { throw "node.exe was not found on PATH." }

$npm = Get-Command npm -ErrorAction SilentlyContinue
if (-not $npm) { throw "npm was not found on PATH." }

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
  "--cooldown-ms", "$CooldownMs",
  "--state-out", $statePath
)

if ($Screenshot) { $nodeArgs += @("--screenshot", $Screenshot) }
if ($ReplyOut) { $nodeArgs += @("--reply-out", $ReplyOut) }
if ($BodyOut) { $nodeArgs += @("--body-out", $BodyOut) }
foreach ($image in $ImagePath) {
  if ($image) { $nodeArgs += @("--image", $image) }
}
if ($ReuseCurrentChat) { $nodeArgs += @("--reuse-current-chat") }
if ($NewChat) { $nodeArgs += @("--new-chat") }
if ($AllowFastSend) { $nodeArgs += @("--allow-fast-send") }

try {
  & $node.Source @nodeArgs
  exit $LASTEXITCODE
} finally {
  $env:NODE_PATH = $oldNodePath
}

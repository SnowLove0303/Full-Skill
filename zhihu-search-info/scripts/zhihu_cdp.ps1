param(
  [ValidateSet("search", "fetch", "hot", "recommend", "question", "answer", "article", "observe")]
  [string]$Mode = "search",
  [string]$Query = "",
  [string]$Url = "",
  [int]$Limit = 10,
  [ValidateSet("all", "answer", "article", "question")]
  [string]$Type = "all",
  [ValidateSet("default", "created")]
  [string]$Sort = "default",
  [int]$MaxContent = 4000,
  [string]$CdpUrl = $(if ($env:CHROME_DIDY_CDP_URL) { $env:CHROME_DIDY_CDP_URL } elseif ([Environment]::GetEnvironmentVariable("CHROME_DIDY_CDP_URL", "User")) { [Environment]::GetEnvironmentVariable("CHROME_DIDY_CDP_URL", "User") } elseif ($env:CHROME_DIDY_CHROME_PORT) { "http://127.0.0.1:$env:CHROME_DIDY_CHROME_PORT" } elseif ([Environment]::GetEnvironmentVariable("CHROME_DIDY_CHROME_PORT", "User")) { "http://127.0.0.1:$([Environment]::GetEnvironmentVariable("CHROME_DIDY_CHROME_PORT", "User"))" } else { "http://127.0.0.1:9222" }),
  [int]$TimeoutMs = 30000,
  [string]$OutJson = "",
  [string]$OutMarkdown = "",
  [switch]$NewTab
)

$ErrorActionPreference = "Stop"

$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) { throw "node.exe was not found on PATH." }

$npm = Get-Command npm -ErrorAction SilentlyContinue
if (-not $npm) { throw "npm was not found on PATH." }

$script = Join-Path $PSScriptRoot "zhihu_cdp.js"
$skillRoot = Split-Path -Parent $PSScriptRoot
$chromeDidySkill = "F:\AIAPP\Codex\.codex\skills\chrome-control-suite"
$runtimeRoot = if ($env:CHROME_DIDY_PLAYWRIGHT_RUNTIME) { $env:CHROME_DIDY_PLAYWRIGHT_RUNTIME } elseif ([Environment]::GetEnvironmentVariable("CHROME_DIDY_PLAYWRIGHT_RUNTIME", "User")) { [Environment]::GetEnvironmentVariable("CHROME_DIDY_PLAYWRIGHT_RUNTIME", "User") } elseif (Test-Path (Join-Path $chromeDidySkill ".runtime\playwright")) { Join-Path $chromeDidySkill ".runtime\playwright" } else { Join-Path $skillRoot ".runtime\playwright" }
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
  $script,
  "--mode", $Mode,
  "--cdp-url", $CdpUrl,
  "--limit", "$Limit",
  "--type", $Type,
  "--sort", $Sort,
  "--max-content", "$MaxContent",
  "--timeout-ms", "$TimeoutMs"
)

if ($Query) { $nodeArgs += @("--query", $Query) }
if ($Url) { $nodeArgs += @("--url", $Url) }
if ($OutJson) { $nodeArgs += @("--out-json", $OutJson) }
if ($OutMarkdown) { $nodeArgs += @("--out-markdown", $OutMarkdown) }
if ($NewTab) { $nodeArgs += "--new-tab" }

try {
  & $node.Source @nodeArgs
  exit $LASTEXITCODE
} finally {
  $env:NODE_PATH = $oldNodePath
}

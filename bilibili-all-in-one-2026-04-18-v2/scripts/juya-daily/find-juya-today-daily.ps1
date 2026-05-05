$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:NODE_OPTIONS = "--no-warnings"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Workspace = if ($env:OPENCLAW_AGENT_WORKSPACE) {
    $env:OPENCLAW_AGENT_WORKSPACE
} else {
    $ScriptDir
}
$ResultPath = if ($env:JUYA_LOOKUP_RESULT) {
    $env:JUYA_LOOKUP_RESULT
} else {
    Join-Path $Workspace "juya-today-daily-result.json"
}
$env:JUYA_LOOKUP_RESULT = $ResultPath
node (Join-Path $ScriptDir "find-juya-today-daily.mjs")

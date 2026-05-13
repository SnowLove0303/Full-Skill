$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:NODE_OPTIONS = "--no-warnings"
node (Join-Path $PSScriptRoot "find-juya-today-daily.mjs")

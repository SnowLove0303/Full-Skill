param(
    [string]$LookupResultPath = $(Join-Path (Get-Location) "juya-today-daily-result.json"),
    [string]$DatabaseId = "34d003b68bec8027a6eafd8b918c72c5",
    [string]$ReportPath = $(Join-Path (Get-Location) "juya-today-fullflow-report.json"),
    [switch]$DryRun
)
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$publisher = Join-Path $PSScriptRoot "write-notion-juya-daily-v2.mjs"
if (-not (Test-Path -LiteralPath $publisher)) {
    Write-Output "NO_NOTION_PUBLISHER: $publisher"
    exit 1
}

$env:JUYA_LOOKUP_RESULT = $LookupResultPath
$env:BILIBILI_FULLFLOW_REPORT = $ReportPath
$env:BILIBILI_DAILY_NOTION_DATABASE_ID = $DatabaseId

$args = @($publisher, "--lookup-result", $LookupResultPath, "--report", $ReportPath, "--database-id", $DatabaseId)
if ($DryRun) {
    $args += "--dry-run"
}

node @args
$exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
if ($exitCode -eq 0) {
    Write-Output "NOTION_DAILY_WRITER_OK"
} else {
    Write-Output "NOTION_DAILY_WRITER_FAILED: $exitCode"
}
exit $exitCode

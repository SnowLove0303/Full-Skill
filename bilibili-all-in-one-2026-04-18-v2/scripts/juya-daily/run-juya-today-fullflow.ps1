$ErrorActionPreference = 'Continue'

function Resolve-FirstExistingPath {
    param(
        [object[]]$Candidates = @(),
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    foreach ($candidate in $Candidates) {
        $candidatePath = [string]$candidate
        if (-not [string]::IsNullOrWhiteSpace($candidatePath) -and (Test-Path -LiteralPath $candidatePath)) {
            return (Resolve-Path -LiteralPath $candidatePath).Path
        }
    }

    throw "Missing required path for ${Name}: $($Candidates -join '; ')"
}

$ScriptDir = $PSScriptRoot
$Workspace = if (-not [string]::IsNullOrWhiteSpace($env:OPENCLAW_AGENT_WORKSPACE)) {
    $env:OPENCLAW_AGENT_WORKSPACE
} else {
    $ScriptDir
}
$LookupScript = Join-Path $ScriptDir 'find-juya-today-daily.ps1'
$LookupResult = Join-Path $Workspace 'juya-today-daily-result.json'
$SkillRoot = if (-not [string]::IsNullOrWhiteSpace($env:BILIBILI_SKILL_ROOT)) {
    $env:BILIBILI_SKILL_ROOT
} else {
    (Resolve-Path -LiteralPath (Join-Path $ScriptDir '..\..')).Path
}
$RunPy = Join-Path $SkillRoot 'scripts\bilibili-opencli\scripts\run.py'
$ReportPath = Join-Path $Workspace 'juya-today-fullflow-report.json'
$NotionDatabaseId = '34d003b6-8bec-8011-b011-000b2dd50557'
$NotionSkillDir = Join-Path $Workspace 'skills\notion-api'
$NotionApiScript = Join-Path $NotionSkillDir 'scripts\notion-api.mjs'

$PythonCandidates = @()
if (-not [string]::IsNullOrWhiteSpace($env:BILIBILI_SKILL_PYTHON)) {
    $PythonCandidates += $env:BILIBILI_SKILL_PYTHON
}
$PythonCandidates += @(
    'E:\MorenAnzhuangLujing\Huangjingdajian\python-venvs\bilibili-all-in-one\Scripts\python.exe',
    'E:\MorenAnzhuangLujing\Huangjingdajian\Python\python.exe'
)
$Python = Resolve-FirstExistingPath -Name 'Python' -Candidates $PythonCandidates

$OpenCliCandidates = @()
if (-not [string]::IsNullOrWhiteSpace($env:OPENCLI_CMD)) {
    $OpenCliCandidates += $env:OPENCLI_CMD
}
$OpenCliCandidates += @(
    'E:\MorenAnzhuangLujing\Huangjingdajian\node-tools\opencli\node_modules\.bin\opencli.cmd'
)
$OpenCli = Resolve-FirstExistingPath -Name 'OpenCLI' -Candidates $OpenCliCandidates

$RunRoot = 'F:\AIAPP\Xiangmu\MutiAgent\runtime\bilibili-fullflow'
$RunId = Get-Date -Format 'yyyyMMdd-HHmmss'
$OutputDir = Join-Path $RunRoot "downloads\$RunId"
$VaultDir = Join-Path $RunRoot "notes\$RunId"

New-Item -ItemType Directory -Path $OutputDir,$VaultDir -Force | Out-Null

$env:OPENCLI_CMD = $OpenCli
$env:BILIBILI_OUTPUT_DIR = $OutputDir
$env:BILIBILI_VAULT_DIR = $VaultDir
$env:JUYA_LOOKUP_RESULT = $LookupResult
$env:BILIBILI_FULLFLOW_REPORT = $ReportPath
$env:BILIBILI_DAILY_NOTION_DATABASE_ID = '34d003b68bec8027a6eafd8b918c72c5'
$env:HF_HOME = 'F:\AIAPP\Xiangmu\MutiAgent\runtime\hf-home'
$env:HF_HUB_CACHE = Join-Path $env:HF_HOME 'hub'
$env:TRANSFORMERS_CACHE = Join-Path $env:HF_HOME 'transformers'
$env:HF_ENDPOINT = if ($env:HF_ENDPOINT) { $env:HF_ENDPOINT } else { 'https://hf-mirror.com' }
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = if ($env:HF_HUB_DISABLE_SYMLINKS_WARNING) { $env:HF_HUB_DISABLE_SYMLINKS_WARNING } else { '1' }
$env:PYTHONUTF8 = if ($env:PYTHONUTF8) { $env:PYTHONUTF8 } else { '1' }
$env:PYTHONIOENCODING = if ($env:PYTHONIOENCODING) { $env:PYTHONIOENCODING } else { 'utf-8' }
$env:WHISPER_DOWNLOAD_ROOT = if ($env:WHISPER_DOWNLOAD_ROOT) {
    $env:WHISPER_DOWNLOAD_ROOT
} else {
    'E:\MorenAnzhuangLujing\Huangjingdajian\tool-caches\huggingface\bilibili-all-in-one\models'
}
$env:TEMP = Join-Path $RunRoot 'tmp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Path $env:TEMP,$env:HF_HOME,$env:HF_HUB_CACHE,$env:TRANSFORMERS_CACHE,$env:WHISPER_DOWNLOAD_ROOT -Force | Out-Null

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command
    )

    $startedAt = Get-Date -Format o
    $global:LASTEXITCODE = $null
    $output = & $Command 2>&1
    $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }

    [pscustomobject]@{
        name = $Name
        exitCode = $exitCode
        startedAt = $startedAt
        finishedAt = Get-Date -Format o
        output = @($output | ForEach-Object { $_.ToString() })
    }
}

function Update-ReportArtifacts {
    $script:report.downloadArtifacts = @(
        if (Test-Path -LiteralPath $OutputDir) {
            Get-ChildItem -LiteralPath $OutputDir -Recurse -Force | Select-Object FullName, Length, LastWriteTime
        }
    )
    $script:report.noteArtifacts = @(
        if (Test-Path -LiteralPath $VaultDir) {
            Get-ChildItem -LiteralPath $VaultDir -Recurse -Force | Select-Object FullName, Length, LastWriteTime
        }
    )
}

function Save-RunReport {
    $script:report | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $ReportPath -Encoding UTF8
}

$report = [ordered]@{
    requestedBy = 'openclaw-agent:bilibili-skill-runner'
    purpose = 'today Juya daily: lookup, download, transcribe, vault note, and Notion daily report'
    workspace = $Workspace
    skillRoot = $SkillRoot
    python = $Python
    openCli = $OpenCli
    runPy = $RunPy
    outputDir = $OutputDir
    vaultDir = $VaultDir
    reportPath = $ReportPath
    notionDatabaseId = $NotionDatabaseId
    notionApiScript = $NotionApiScript
    startedAt = Get-Date -Format o
    steps = @()
}

$report.steps += Invoke-Step -Name 'lookup_juya_today_daily' -Command {
    powershell -NoProfile -ExecutionPolicy Bypass -File $LookupScript
}

if (Test-Path -LiteralPath $LookupResult) {
    $lookup = Get-Content -LiteralPath $LookupResult -Raw -Encoding UTF8 | ConvertFrom-Json
    $report.lookup = $lookup.result
    $TargetBvid = [string]$lookup.result.bvid
} else {
    $TargetBvid = ''
}

if ([string]::IsNullOrWhiteSpace($TargetBvid)) {
    $report.finishedAt = Get-Date -Format o
    $report.success = $false
    $report.error = 'No BVID resolved for today Juya daily.'
    Save-RunReport
    exit 1
}

$report.targetBvid = $TargetBvid

$report.steps += Invoke-Step -Name 'check_env' -Command {
    powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $SkillRoot 'scripts\check_env.ps1')
}

$report.steps += Invoke-Step -Name 'fullflow_bvid_download_transcribe_note' -Command {
    & $Python $RunPy `
        --bvid $TargetBvid `
        --limit 1 `
        --output $OutputDir `
        --vault $VaultDir `
        --parallel 1 `
        --engine auto `
        --keep-cache
}

Update-ReportArtifacts
$report.interimSavedAt = Get-Date -Format o
Save-RunReport

if ($report.steps | Where-Object { $_.exitCode -ne 0 }) {
    $report.steps += [pscustomobject]@{
        name = 'write_notion_daily_report'
        exitCode = 1
        startedAt = Get-Date -Format o
        finishedAt = Get-Date -Format o
        output = @('SKIPPED: prior lookup/env/fullflow step failed')
    }
} else {
    $report.steps += Invoke-Step -Name 'write_notion_daily_report' -Command {
        powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ScriptDir 'write-notion-juya-daily.ps1') -LookupResultPath $LookupResult -DatabaseId $env:BILIBILI_DAILY_NOTION_DATABASE_ID -ReportPath $ReportPath
    }
}

Update-ReportArtifacts
$report.notionStep = $report.steps | Where-Object { $_.name -eq 'write_notion_daily_report' } | Select-Object name, exitCode, startedAt, finishedAt, @{N='output';E={$_.output | Select-Object -First 5}}
$report.finishedAt = Get-Date -Format o
$report.success = -not ($report.steps | Where-Object { $_.exitCode -ne 0 })

Save-RunReport

if ($report.success) {
    $notionStep = $report.steps | Where-Object { $_.name -eq 'write_notion_daily_report' }
    $notionStatus = if ($notionStep) { if ($notionStep.exitCode -eq 0) { 'OK' } else { 'FAILED' } } else { 'SKIPPED' }
    Write-Output "JUYA_FULLFLOW_OK"
    Write-Output "BVID=$TargetBvid"
    Write-Output "NOTION_STATUS=$notionStatus"
    Write-Output "REPORT=$ReportPath"
    exit 0
}

Write-Output "JUYA_FULLFLOW_FAILED"
Write-Output "BVID=$TargetBvid"
Write-Output "REPORT=$ReportPath"
exit 1

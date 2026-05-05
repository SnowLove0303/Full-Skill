$ErrorActionPreference = 'Continue'

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONUTF8 = if ($env:PYTHONUTF8) { $env:PYTHONUTF8 } else { '1' }
$env:PYTHONIOENCODING = if ($env:PYTHONIOENCODING) { $env:PYTHONIOENCODING } else { 'utf-8' }

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
        if (-not [string]::IsNullOrWhiteSpace($candidatePath) -and $candidatePath -notmatch '[\\/]') {
            $command = Get-Command $candidatePath -ErrorAction SilentlyContinue
            if ($command -and $command.Source) {
                return $command.Source
            }
        }
    }

    throw "Missing required path for ${Name}: $($Candidates -join '; ')"
}

function Resolve-OptionalPath {
    param([object[]]$Candidates = @())

    foreach ($candidate in $Candidates) {
        $candidatePath = [string]$candidate
        if (-not [string]::IsNullOrWhiteSpace($candidatePath) -and (Test-Path -LiteralPath $candidatePath)) {
            return (Resolve-Path -LiteralPath $candidatePath).Path
        }
    }

    return ''
}

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
    if ($output | Where-Object { $_ -is [System.Management.Automation.ErrorRecord] }) {
        $exitCode = if ($exitCode -ne 0) { $exitCode } else { 1 }
    }

    [pscustomobject]@{
        name = $Name
        exitCode = $exitCode
        startedAt = $startedAt
        finishedAt = Get-Date -Format o
        output = @($output | ForEach-Object { $_.ToString() })
    }
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillRootFromScript = Split-Path -Parent (Split-Path -Parent $ScriptDir)

$Workspace = if ($env:OPENCLAW_AGENT_WORKSPACE) {
    $env:OPENCLAW_AGENT_WORKSPACE
} else {
    $SkillRootFromScript
}
$Workspace = (Resolve-Path -LiteralPath $Workspace).Path

$LookupScript = Resolve-FirstExistingPath -Name 'Juya lookup script' -Candidates @(
    (Join-Path $ScriptDir 'find-juya-today-daily.ps1'),
    (Join-Path $Workspace 'find-juya-today-daily.ps1')
)
$LookupResult = Join-Path $Workspace 'juya-today-daily-result.json'

$SkillRoot = Resolve-FirstExistingPath -Name 'bilibili-all-in-one skill root' -Candidates @(
    $env:BILIBILI_ALL_IN_ONE_SKILL_ROOT,
    $SkillRootFromScript,
    'F:\AIAPP\Codex\.codex\skills\bilibili-all-in-one-2026-04-18-v2',
    (Join-Path $Workspace 'skills\bilibili-all-in-one')
)
$RunPy = Join-Path $SkillRoot 'scripts\bilibili-opencli\scripts\run.py'
if (-not (Test-Path -LiteralPath $RunPy)) {
    throw "Missing run.py at $RunPy"
}

$ReportPath = if ($env:JUYA_FULLFLOW_REPORT) {
    $env:JUYA_FULLFLOW_REPORT
} else {
    Join-Path $Workspace 'juya-today-fullflow-report.json'
}

$Python = Resolve-FirstExistingPath -Name 'Python' -Candidates @(
    $env:BILIBILI_SKILL_PYTHON,
    'E:\MorenAnzhuangLujing\Huangjingdajian\python-venvs\bilibili-all-in-one\Scripts\python.exe',
    'E:\MorenAnzhuangLujing\Huangjingdajian\Python\python.exe',
    'python'
)

$OpenCli = Resolve-FirstExistingPath -Name 'OpenCLI' -Candidates @(
    $env:OPENCLI_CMD,
    'E:\MorenAnzhuangLujing\Huangjingdajian\node-tools\opencli\node_modules\.bin\opencli.cmd',
    'opencli.cmd',
    'opencli'
)

$RunRoot = if ($env:BILIBILI_FULLFLOW_RUNTIME_ROOT) {
    $env:BILIBILI_FULLFLOW_RUNTIME_ROOT
} else {
    'F:\AIAPP\Xiangmu\MutiAgent\runtime\bilibili-fullflow'
}
$RunId = if ($env:BILIBILI_FULLFLOW_RUN_ID) {
    $env:BILIBILI_FULLFLOW_RUN_ID
} else {
    Get-Date -Format 'yyyyMMdd-HHmmss'
}
$OutputDir = Join-Path $RunRoot "downloads\$RunId"
$VaultDir = Join-Path $RunRoot "notes\$RunId"

New-Item -ItemType Directory -Path $OutputDir,$VaultDir -Force | Out-Null

$env:OPENCLI_CMD = $OpenCli
$env:BILIBILI_OUTPUT_DIR = $OutputDir
$env:BILIBILI_VAULT_DIR = $VaultDir
$env:HF_HOME = if ($env:HF_HOME) { $env:HF_HOME } else { Join-Path $RunRoot 'hf-home' }
$env:HF_HUB_CACHE = if ($env:HF_HUB_CACHE) { $env:HF_HUB_CACHE } else { Join-Path $env:HF_HOME 'hub' }
$env:TRANSFORMERS_CACHE = if ($env:TRANSFORMERS_CACHE) { $env:TRANSFORMERS_CACHE } else { Join-Path $env:HF_HOME 'transformers' }
$env:HF_ENDPOINT = if ($env:HF_ENDPOINT) { $env:HF_ENDPOINT } else { 'https://hf-mirror.com' }
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = if ($env:HF_HUB_DISABLE_SYMLINKS_WARNING) { $env:HF_HUB_DISABLE_SYMLINKS_WARNING } else { '1' }
$env:WHISPER_DOWNLOAD_ROOT = if ($env:WHISPER_DOWNLOAD_ROOT) {
    $env:WHISPER_DOWNLOAD_ROOT
} else {
    Join-Path $RunRoot 'models'
}
$env:TEMP = if ($env:BILIBILI_FULLFLOW_TMP) { $env:BILIBILI_FULLFLOW_TMP } else { Join-Path $RunRoot 'tmp' }
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Path $env:TEMP,$env:HF_HOME,$env:HF_HUB_CACHE,$env:TRANSFORMERS_CACHE,$env:WHISPER_DOWNLOAD_ROOT -Force | Out-Null

$report = [ordered]@{
    version = 'V3'
    requestedBy = if ($env:OPENCLAW_AGENT_NAME) { "openclaw-agent:$($env:OPENCLAW_AGENT_NAME)" } else { 'local-or-openclaw-agent' }
    purpose = 'Juya daily full Bilibili skill flow: strict lookup, download, transcribe, generate note, optional Notion publish'
    workspace = "$Workspace"
    skillRoot = $SkillRoot
    python = $Python
    openCli = $OpenCli
    runPy = $RunPy
    outputDir = $OutputDir
    vaultDir = $VaultDir
    reportPath = $ReportPath
    startedAt = Get-Date -Format o
    steps = @()
}

$report.steps += Invoke-Step -Name 'lookup_juya_today_daily_strict' -Command {
    powershell -NoProfile -ExecutionPolicy Bypass -File $LookupScript
}

if (Test-Path -LiteralPath $LookupResult) {
    $lookup = Get-Content -LiteralPath $LookupResult -Raw -Encoding UTF8 | ConvertFrom-Json
    $report.lookup = $lookup.result
    $TargetBvid = [string]$lookup.result.bvid
    $LookupEligible = [bool]$lookup.result.validation.eligible
} else {
    $TargetBvid = ''
    $LookupEligible = $false
}

if ([string]::IsNullOrWhiteSpace($TargetBvid) -or -not $LookupEligible) {
    $report.finishedAt = Get-Date -Format o
    $report.success = $false
    $report.error = 'No eligible Juya daily BVID resolved. Refuse to continue to prevent wrong-video execution.'
    $report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $ReportPath -Encoding UTF8
    Write-Output "JUYA_FULLFLOW_BLOCKED"
    Write-Output "REPORT=$ReportPath"
    exit 1
}

$report.targetBvid = $TargetBvid
$CheckEnvScript = Resolve-OptionalPath -Candidates @((Join-Path $SkillRoot 'scripts\check_env.ps1'))
if ($CheckEnvScript) {
    $report.steps += Invoke-Step -Name 'check_env' -Command {
        powershell -NoProfile -ExecutionPolicy Bypass -File $CheckEnvScript
    }
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

$report.downloadArtifacts = @(
    if (Test-Path -LiteralPath $OutputDir) {
        Get-ChildItem -LiteralPath $OutputDir -Recurse -Force | Select-Object FullName, Length, LastWriteTime
    }
)
$report.noteArtifacts = @(
    if (Test-Path -LiteralPath $VaultDir) {
        Get-ChildItem -LiteralPath $VaultDir -Recurse -Force | Select-Object FullName, Length, LastWriteTime
    }
)
$report.finishedAt = Get-Date -Format o
$report.success = -not ($report.steps | Where-Object { $_.exitCode -ne 0 })
$report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $ReportPath -Encoding UTF8

$PublishScript = Resolve-OptionalPath -Candidates @(
    (Join-Path $ScriptDir 'publish-juya-fullflow-result-to-notion.mjs'),
    (Join-Path $Workspace 'publish-juya-fullflow-result-to-notion.mjs')
)
if ($PublishScript -and $env:JUYA_WRITE_NOTION -ne '0') {
    $env:JUYA_FULLFLOW_REPORT = $ReportPath
    $env:JUYA_LOOKUP_RESULT = $LookupResult
    $env:OPENCLAW_AGENT_WORKSPACE = "$Workspace"
    $report.steps += Invoke-Step -Name 'publish_individual_notion_daily' -Command {
        node $PublishScript
    }
}

$report.finishedAt = Get-Date -Format o
$report.success = -not ($report.steps | Where-Object { $_.exitCode -ne 0 })

$report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $ReportPath -Encoding UTF8

if ($report.success) {
    Write-Output "JUYA_FULLFLOW_OK"
    Write-Output "BVID=$TargetBvid"
    Write-Output "REPORT=$ReportPath"
    exit 0
}

Write-Output "JUYA_FULLFLOW_FAILED"
Write-Output "BVID=$TargetBvid"
Write-Output "REPORT=$ReportPath"
exit 1

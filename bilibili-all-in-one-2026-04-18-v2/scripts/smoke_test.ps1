param(
    [string]$SkillRoot,
    [string]$InstallRoot = "E:\MorenAnzhuangLujing\Huangjingdajian",
    [string]$Query = "bilibili",
    [string]$Uid = "285286947",
    [switch]$TestOpencliWorkflow
)

$ErrorActionPreference = "Stop"

if (-not $SkillRoot) {
    $SkillRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
}

$EnvFile = Join-Path $SkillRoot ".env.generated.ps1"
if (Test-Path $EnvFile) {
    . $EnvFile
}

$env:PYTHONIOENCODING = "utf-8"

$VenvPython = Join-Path $InstallRoot "python-venvs\bilibili-all-in-one\Scripts\python.exe"
$PythonExe = if (Test-Path $VenvPython) { $VenvPython } else { "python" }
$ScriptDir = Join-Path $SkillRoot "scripts\bilibili-opencli\scripts"
$RunPy = Join-Path $SkillRoot "scripts\bilibili-opencli\scripts\run.py"

Write-Host "[Smoke] Python syntax"
& $PythonExe -m py_compile `
    (Join-Path $SkillRoot "scripts\bilibili-opencli\scripts\bilibili_utils.py") `
    (Join-Path $SkillRoot "scripts\bilibili-opencli\scripts\run.py") `
    (Join-Path $SkillRoot "scripts\bilibili-opencli\scripts\download.py") `
    (Join-Path $SkillRoot "scripts\bilibili-opencli\scripts\formatter.py") `
    (Join-Path $SkillRoot "scripts\bilibili-opencli\scripts\transcribe.py")

Write-Host "[Smoke] Search dry-run: $Query"
$SavedOpencli = $env:OPENCLI_CMD
$SavedDisableOpencli = $env:BILIBILI_DISABLE_OPENCLI
Remove-Item Env:OPENCLI_CMD -ErrorAction SilentlyContinue
$env:BILIBILI_DISABLE_OPENCLI = "1"
@'
import sys
sys.path.insert(0, sys.argv[1])
from search import search

videos = search(sys.argv[2], limit=2)
print(f"[OK] Workflow search returned {len(videos)} videos")
if not videos:
    raise SystemExit(2)
'@ | & $PythonExe - $ScriptDir $Query
& $PythonExe $RunPy --search $Query --limit 2 --dry-run

Write-Host "[Smoke] Site-search matching"
& $PythonExe $RunPy `
    --find-video "bilibili" `
    --limit 10 `
    --strict-find `
    --dry-run
if ($LASTEXITCODE -ne 0) {
    throw "Site-search smoke test failed."
}
if ($SavedOpencli) {
    $env:OPENCLI_CMD = $SavedOpencli
}
if ($SavedDisableOpencli) {
    $env:BILIBILI_DISABLE_OPENCLI = $SavedDisableOpencli
} else {
    Remove-Item Env:BILIBILI_DISABLE_OPENCLI -ErrorAction SilentlyContinue
}

if ($env:OPENCLI_CMD -and (Test-Path $env:OPENCLI_CMD)) {
    Write-Host "[Smoke] OpenCLI version"
    & $env:OPENCLI_CMD --version
}

if ($TestOpencliWorkflow -and $env:OPENCLI_CMD -and (Test-Path $env:OPENCLI_CMD)) {
    Write-Host "[Smoke] UP dry-run via OPENCLI_CMD: $Uid"
    & $PythonExe $RunPy --uid $Uid --limit 2 --dry-run
} elseif ($TestOpencliWorkflow) {
    Write-Host "[Skip] OPENCLI_CMD is not configured; skipping UP dry-run."
}

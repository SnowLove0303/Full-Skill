param(
    [string]$SkillRoot,
    [string]$InstallRoot = "E:\MorenAnzhuangLujing\Huangjingdajian",
    [int]$Port = 9222,
    [int]$WaitSeconds = 180,
    [string]$ProfileDir,
    [string]$ChromePath
)

$ErrorActionPreference = "Stop"

if (-not $SkillRoot) {
    $SkillRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).Path
}

$EnvFile = Join-Path $SkillRoot ".env.generated.ps1"
if (Test-Path $EnvFile) {
    . $EnvFile
}

$VenvPython = Join-Path $InstallRoot "python-venvs\bilibili-all-in-one\Scripts\python.exe"
$PythonExe = if (Test-Path $VenvPython) { $VenvPython } else { "python" }
$Cli = Join-Path $SkillRoot "scripts\bilibili-expander\cli.py"

$ArgsList = @(
    $Cli,
    "chrome-login",
    "--port", "$Port",
    "--wait-login", "$WaitSeconds"
)

if ($ProfileDir) {
    $ArgsList += @("--profile-dir", $ProfileDir)
}

if ($ChromePath) {
    $ArgsList += @("--chrome-path", $ChromePath)
}

& $PythonExe @ArgsList

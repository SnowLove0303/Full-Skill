param(
    [string]$InstallRoot = "E:\MorenAnzhuangLujing\Huangjingdajian",
    [string]$SkillRoot,
    [switch]$SkipPythonDeps,
    [switch]$SkipOpencli,
    [switch]$PersistUserEnv,
    [switch]$RunSmokeTest
)

$ErrorActionPreference = "Stop"

function Resolve-SkillRoot {
    param([string]$Value)
    if ($Value) {
        return (Resolve-Path -LiteralPath $Value).Path
    }
    return (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
}

function Set-ScopedEnv {
    param(
        [string]$Name,
        [string]$Value,
        [switch]$Persist
    )
    Set-Item -Path "Env:$Name" -Value $Value
    if ($Persist) {
        [Environment]::SetEnvironmentVariable($Name, $Value, "User")
    }
}

$SkillRoot = Resolve-SkillRoot $SkillRoot
$VenvDir = Join-Path $InstallRoot "python-venvs\bilibili-all-in-one"
$PipCache = Join-Path $InstallRoot "tool-caches\pip\bilibili-all-in-one"
$HfHome = Join-Path $InstallRoot "tool-caches\huggingface\bilibili-all-in-one"
$TorchHome = Join-Path $InstallRoot "tool-caches\torch\bilibili-all-in-one"
$WhisperRoot = Join-Path $HfHome "models"
$NpmPrefix = Join-Path $InstallRoot "node-tools\opencli"
$NpmCache = Join-Path $InstallRoot "tool-caches\npm\opencli"
$OutputDir = Join-Path $InstallRoot "downloads\bilibili"

$dirs = @($VenvDir, $PipCache, $HfHome, $TorchHome, $WhisperRoot, $NpmPrefix, $NpmCache, $OutputDir)
foreach ($dir in $dirs) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}

Set-ScopedEnv "PIP_CACHE_DIR" $PipCache -Persist:$PersistUserEnv
Set-ScopedEnv "HF_HOME" $HfHome -Persist:$PersistUserEnv
Set-ScopedEnv "TORCH_HOME" $TorchHome -Persist:$PersistUserEnv
Set-ScopedEnv "WHISPER_DOWNLOAD_ROOT" $WhisperRoot -Persist:$PersistUserEnv
Set-ScopedEnv "WHISPER_MODEL_NAME" "tiny" -Persist:$PersistUserEnv
Set-ScopedEnv "BILIBILI_OUTPUT_DIR" $OutputDir -Persist:$PersistUserEnv

if (-not $SkipPythonDeps) {
    if (-not (Test-Path (Join-Path $VenvDir "Scripts\python.exe"))) {
        python -m venv $VenvDir
    }
    $PythonExe = Join-Path $VenvDir "Scripts\python.exe"
    & $PythonExe -m pip install --upgrade pip
    & $PythonExe -m pip install yt-dlp imageio-ffmpeg faster-whisper
}

if (-not $SkipOpencli) {
    npm --prefix $NpmPrefix --cache $NpmCache install @jackwener/opencli
    $OpencliCmd = Join-Path $NpmPrefix "node_modules\.bin\opencli.cmd"
    if (Test-Path $OpencliCmd) {
        Set-ScopedEnv "OPENCLI_CMD" $OpencliCmd -Persist:$PersistUserEnv
    }
}

$EnvFile = Join-Path $SkillRoot ".env.generated.ps1"
$lines = @(
    "`$env:PIP_CACHE_DIR = `"$PipCache`""
    "`$env:HF_HOME = `"$HfHome`""
    "`$env:TORCH_HOME = `"$TorchHome`""
    "`$env:WHISPER_DOWNLOAD_ROOT = `"$WhisperRoot`""
    "`$env:WHISPER_MODEL_NAME = `"tiny`""
    "`$env:BILIBILI_OUTPUT_DIR = `"$OutputDir`""
)
if (Test-Path (Join-Path $NpmPrefix "node_modules\.bin\opencli.cmd")) {
    $OpencliEnv = Join-Path $NpmPrefix "node_modules\.bin\opencli.cmd"
    $lines += "`$env:OPENCLI_CMD = `"$OpencliEnv`""
}
[string]::Join([Environment]::NewLine, $lines) + [Environment]::NewLine |
    Set-Content -LiteralPath $EnvFile -Encoding UTF8

Write-Host "[OK] Bilibili skill setup complete"
Write-Host "SkillRoot: $SkillRoot"
Write-Host "Python venv: $VenvDir"
Write-Host "OpenCLI: $($env:OPENCLI_CMD)"
Write-Host "Output: $OutputDir"
Write-Host "Env file: $EnvFile"

if ($RunSmokeTest) {
    & (Join-Path $PSScriptRoot "smoke_test.ps1") -SkillRoot $SkillRoot -InstallRoot $InstallRoot
}

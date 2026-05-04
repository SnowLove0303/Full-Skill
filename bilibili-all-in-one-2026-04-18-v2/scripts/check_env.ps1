param(
    [string]$InstallRoot = "E:\MorenAnzhuangLujing\Huangjingdajian",
    [string]$SkillRoot
)

$ErrorActionPreference = "Stop"

if (-not $SkillRoot) {
    $SkillRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
}

$VenvPython = Join-Path $InstallRoot "python-venvs\bilibili-all-in-one\Scripts\python.exe"
$OpencliCmd = $env:OPENCLI_CMD
if (-not $OpencliCmd) {
    $Candidate = Join-Path $InstallRoot "node-tools\opencli\node_modules\.bin\opencli.cmd"
    if (Test-Path $Candidate) {
        $OpencliCmd = $Candidate
    }
}

$checks = [ordered]@{
    SkillRoot = (Test-Path $SkillRoot)
    Python = [bool](Get-Command python -ErrorAction SilentlyContinue)
    VenvPython = (Test-Path $VenvPython)
    OpenCLI = ($OpencliCmd -and (Test-Path $OpencliCmd))
    OutputDir = (Test-Path (Join-Path $InstallRoot "downloads\bilibili"))
    WhisperDownloadRoot = (Test-Path (Join-Path $InstallRoot "tool-caches\huggingface\bilibili-all-in-one\models"))
}

foreach ($item in $checks.GetEnumerator()) {
    $status = if ($item.Value) { "OK" } else { "MISS" }
    Write-Host ("[{0}] {1}" -f $status, $item.Key)
}

if (Test-Path $VenvPython) {
@'
import importlib.util
for name in ["yt_dlp", "imageio_ffmpeg", "faster_whisper"]:
    print(f"[{'OK' if importlib.util.find_spec(name) else 'MISS'}] python:{name}")
'@ | & $VenvPython -
}

if ($OpencliCmd -and (Test-Path $OpencliCmd)) {
    & $OpencliCmd --version
}

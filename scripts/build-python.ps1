param(
    [string]$Python = "python",
    [string]$WorkRoot = "H:\CodexTemp\work\neon-arrow-nexus\pyinstaller",
    [string]$TempRoot = ""
)

$ErrorActionPreference = "Stop"

if (-not $TempRoot) {
    if ($env:RUNNER_TEMP) {
        $TempRoot = Join-Path $env:RUNNER_TEMP "neon-arrow-temp"
    } elseif (Test-Path -LiteralPath "H:\") {
        $TempRoot = "H:\CodexTemp\tmp"
    } else {
        $TempRoot = Join-Path ([System.IO.Path]::GetTempPath()) "neon-arrow-temp"
    }
}

$env:TEMP = $TempRoot
$env:TMP = $TempRoot
$env:PYINSTALLER_CONFIG_DIR = "$WorkRoot\config"

New-Item -ItemType Directory -Force -Path $TempRoot | Out-Null
New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null
New-Item -ItemType Directory -Force -Path "dist" | Out-Null

& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --manifest "$PSScriptRoot\windows-app.manifest" `
    --name "NeonArrowNexus-Python" `
    --distpath "dist" `
    --workpath "$WorkRoot\build" `
    --specpath "$WorkRoot\spec" `
    "main.py"

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE"
}

Write-Host "Built: dist\NeonArrowNexus-Python.exe"

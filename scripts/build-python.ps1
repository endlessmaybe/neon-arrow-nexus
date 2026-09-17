param(
    [string]$Python = "python",
    [string]$WorkRoot = "H:\CodexTemp\work\neon-arrow-nexus\pyinstaller"
)

$ErrorActionPreference = "Stop"
$env:TEMP = "H:\CodexTemp\tmp"
$env:TMP = "H:\CodexTemp\tmp"
$env:PYINSTALLER_CONFIG_DIR = "$WorkRoot\config"

New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null
New-Item -ItemType Directory -Force -Path "dist" | Out-Null

& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name "NeonArrowNexus-Python" `
    --distpath "dist" `
    --workpath "$WorkRoot\build" `
    --specpath "$WorkRoot\spec" `
    "main.py"

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE"
}

Write-Host "Built: dist\NeonArrowNexus-Python.exe"

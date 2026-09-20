param(
    [string]$Version = "v1.0.0",
    [string]$OutputRoot = "H:\CodexTemp\work\neon-arrow-nexus\release"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$exe = Join-Path $repoRoot "dist\NeonArrowNexus-Python.exe"
$launcherEn = Join-Path $repoRoot "launch_game.bat"
$secondaryLauncher = Get-ChildItem -LiteralPath $repoRoot -Filter "*.bat" -File |
    Where-Object { $_.Name -ne "launch_game.bat" } |
    Select-Object -First 1

foreach ($required in @($exe, $launcherEn)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required release file is missing: $required"
    }
}
if (-not $secondaryLauncher) {
    throw "The secondary double-click launcher BAT is missing."
}

$stage = Join-Path $OutputRoot "NeonArrowNexus-$Version-Windows-x64"
$zip = "$stage.zip"

if (Test-Path -LiteralPath $stage) {
    Remove-Item -LiteralPath $stage -Recurse -Force
}
if (Test-Path -LiteralPath $zip) {
    Remove-Item -LiteralPath $zip -Force
}

New-Item -ItemType Directory -Force -Path (Join-Path $stage "dist") | Out-Null
Copy-Item -LiteralPath $exe -Destination (Join-Path $stage "dist\NeonArrowNexus-Python.exe")
Copy-Item -LiteralPath $launcherEn -Destination (Join-Path $stage "launch_game.bat")
Copy-Item -LiteralPath $secondaryLauncher.FullName -Destination $stage

$readme = @"
Neon Arrow Nexus $Version

How to run:
1. Extract the whole ZIP to a normal folder first.
2. Double-click either BAT launcher, or run dist\NeonArrowNexus-Python.exe directly.
3. This is a self-contained Windows x64 build. Python is not required.

If a BAT window closes immediately:
- Do not run files from inside the ZIP preview. Extract everything first.
- Keep the dist folder beside the BAT launchers.
- If Windows blocks the downloaded EXE, open the EXE Properties page,
  choose Unblock when that option is present, and run it again.

Project page:
https://github.com/endlessmaybe/neon-arrow-nexus
"@

[System.IO.File]::WriteAllText(
    (Join-Path $stage "README.txt"),
    $readme,
    [System.Text.UTF8Encoding]::new($true)
)

New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
Compress-Archive -LiteralPath $stage -DestinationPath $zip -CompressionLevel Optimal

$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $zip).Hash.ToLowerInvariant()
$size = (Get-Item -LiteralPath $zip).Length

[pscustomobject]@{
    Version = $Version
    Zip = $zip
    SizeBytes = $size
    Sha256 = $hash
} | ConvertTo-Json -Depth 3

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Missing .venv. Follow README.md to install dependencies first."
}

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name "StarryPocket" `
    --icon "assets\icon.ico" `
    --add-data "assets;assets" `
    "main.py"
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed."
}

$release = Join-Path $PSScriptRoot "dist\StarryPocket"
$quarantine = Join-Path $PSScriptRoot "build\unused-runtime"
New-Item -ItemType Directory -Force -Path $quarantine | Out-Null

# Qt should use the matching ICU runtime supplied by Windows.
foreach ($runtimeFile in @("icuuc.dll", "icudt78.dll")) {
    $source = Join-Path $release "_internal\$runtimeFile"
    if (Test-Path -LiteralPath $source) {
        Move-Item -LiteralPath $source -Destination $quarantine -Force
    }
}

Copy-Item -LiteralPath (Join-Path $PSScriptRoot "messages.json") -Destination $release -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "README.md") -Destination $release -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "LICENSE") -Destination $release -Force

$archive = Join-Path $PSScriptRoot "dist\StarryPocket-Windows-x64.zip"
if (Test-Path -LiteralPath $archive) {
    Remove-Item -LiteralPath $archive -Force
}
Compress-Archive -Path $release -DestinationPath $archive -CompressionLevel Optimal

Write-Host ""
Write-Host "Build complete: $archive"

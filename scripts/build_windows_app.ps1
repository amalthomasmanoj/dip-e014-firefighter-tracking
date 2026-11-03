$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$buildEnv = Join-Path $repoRoot ".build-windows-venv"
$python = Join-Path $buildEnv "Scripts\python.exe"
$pyinstaller = Join-Path $buildEnv "Scripts\pyinstaller.exe"

Push-Location (Join-Path $repoRoot "ui\web")
try {
    npm ci
    npm run build
}
finally {
    Pop-Location
}

if (-not (Test-Path $python)) {
    python -m venv $buildEnv
}
& $python -m pip install --upgrade pip
& $python -m pip install -e "$repoRoot[heart-rate,desktop]" pyinstaller

Push-Location $repoRoot
try {
    & $pyinstaller `
        --noconfirm `
        --clean `
        --onefile `
        --windowed `
        --name "E014-Firefighter-Tracking" `
        --add-data "ui/web/dist;ui_dist" `
        --add-data "desktop/responders.default.yaml;desktop_config" `
        --collect-submodules backend `
        --collect-submodules tools `
        --collect-submodules webview `
        desktop/macos_app.py
}
finally {
    Pop-Location
}

Write-Host "Built: $repoRoot\dist\E014-Firefighter-Tracking.exe"

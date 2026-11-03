#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
build_env="$repo_root/.build-macos-venv"

cd "$repo_root/ui/web"
npm ci
npm run build

python3 -m venv "$build_env"
"$build_env/bin/python" -m pip install --upgrade pip
"$build_env/bin/python" -m pip install -e "$repo_root[heart-rate,desktop]" pyinstaller

cd "$repo_root"
"$build_env/bin/pyinstaller" \
  --noconfirm \
  --clean \
  --windowed \
  --name "E014 Firefighter Tracking" \
  --add-data "ui/web/dist:ui_dist" \
  --add-data "desktop/responders.default.yaml:desktop_config" \
  --collect-submodules backend \
  --collect-submodules tools \
  --collect-submodules webview \
  desktop/macos_app.py

app_plist="$repo_root/dist/E014 Firefighter Tracking.app/Contents/Info.plist"
/usr/libexec/PlistBuddy -c \
  "Add :NSBluetoothAlwaysUsageDescription string Connect to the firefighter heart-rate strap." \
  "$app_plist" 2>/dev/null || /usr/libexec/PlistBuddy -c \
  "Set :NSBluetoothAlwaysUsageDescription Connect to the firefighter heart-rate strap." \
  "$app_plist"
codesign --force --deep --sign - "$repo_root/dist/E014 Firefighter Tracking.app"

echo "Built: $repo_root/dist/E014 Firefighter Tracking.app"

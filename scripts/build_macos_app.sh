#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
build_env="$repo_root/.build-macos-venv"

cd "$repo_root/ui/web"
npm ci
npm run build

python3 -m venv "$build_env"
"$build_env/bin/python" -m pip install --upgrade pip
"$build_env/bin/python" -m pip install -e "$repo_root[heart-rate]" pyinstaller

cd "$repo_root"
"$build_env/bin/pyinstaller" \
  --noconfirm \
  --clean \
  --windowed \
  --name "E014 Firefighter Tracking" \
  --add-data "ui/web/dist:ui_dist" \
  --collect-submodules backend \
  --collect-submodules tools \
  desktop/macos_app.py

echo "Built: $repo_root/dist/E014 Firefighter Tracking.app"

#!/bin/sh
# Lokal tekshiruv: backend testlari + admin type-check + build.
# CI'da ham shu qadamlar ishlatiladi (GitHub Actions workflow qo'shilsa).
set -eu

cd "$(dirname "$0")/.."
ROOT=$(pwd)

echo "== Backend testlari =="
cd "$ROOT/backend"
python3 -m pytest -q

echo "== Admin type-check =="
cd "$ROOT/admin"
npx tsc --noEmit

echo "== Admin build =="
npx vite build

echo "Hammasi o'tdi."

#!/bin/sh
set -eu

# Skript qayerdan chaqirilishidan qat'i nazar, Vite admin/ papkasida ishlaydi.
cd "$(dirname "$0")/../admin"

# npm topilmasa, nvm'dagi standart yo'lga qaytamiz.
if command -v npm >/dev/null 2>&1; then
	npm=$(command -v npm)
else
	npm=/home/saidov/.nvm/versions/node/v20.20.2/bin/npm
fi

while :; do
	if address=$("/usr/bin/tailscale" ip -4 2>/dev/null) && [ -n "$address" ]; then
		break
	fi
	sleep 2
done

exec "$npm" run dev -- --host "$address" --port 5173

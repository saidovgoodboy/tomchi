#!/bin/sh
set -eu

tailscale=/usr/bin/tailscale
npm=/home/saidov/.nvm/versions/node/v20.20.2/bin/npm

while :; do
	if address=$("$tailscale" ip -4 2>/dev/null) && [ -n "$address" ]; then
		break
	fi
	sleep 2
done

exec "$npm" run dev -- --host "$address" --port 5173

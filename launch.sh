#!/bin/bash
# =============================================================
# CGS Kitchen Display — Kiosk Launch Script (Raspberry Pi Zero 2 W)
#
# ONE script for BOTH display units. Role ($1 or /etc/celtech/role)
# selects which app dir to launch:
#   ./launch.sh expo  -> celtech-expo/dist/index.html
#   ./launch.sh menu  -> celtech-menu/dist/index.html
#
# These are output-only TVs: NO --touch-events, and the cursor
# is hidden (the apps also set `cursor: none`, this is belt-and-
# suspenders for the brief pre-paint window).
# =============================================================
sleep 5

ROLE="${1:-}"
if [ -z "$ROLE" ] && [ -f /etc/celtech/role ]; then
    ROLE="$(cat /etc/celtech/role | tr -d '[:space:]')"
fi

case "$ROLE" in
    expo) APP_NAME="celtech-expo" ;;
    menu) APP_NAME="celtech-menu" ;;
    *)    echo "ERROR: role must be 'expo' or 'menu' (got '$ROLE')."; exit 1 ;;
esac

exec chromium \
  --kiosk \
  --noerrdialogs \
  --disable-infobars \
  --no-first-run \
  --ozone-platform=wayland \
  --password-store=basic \
  --allow-file-access-from-files \
  --enable-features=UseOzonePlatform \
  --force-device-scale-factor=1 \
  --disable-session-crashed-bubble \
  --disable-popup-blocking \
  --app=file:///home/druid-display/$APP_NAME/dist/index.html

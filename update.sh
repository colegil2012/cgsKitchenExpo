#!/bin/bash
# =============================================================
# CGS Kitchen Display — Update Script (Pi Zero 2 W, NATIVE)
#
# Compare this to the old Vue version:
#   OLD: git pull -> write .env -> npm ci -> npm run build (50s, needed
#        1GB swap, memory-guarded, and STILL couldn't run the browser)
#   NEW: git pull -> restart the service. That's it.
#
# The Python app reads /etc/celtech/env at RUNTIME, so there is no build
# step and no Node toolchain on the device at all.
#
#   ./update.sh expo   -> tracks cgsKitchenExpo
#   ./update.sh menu   -> tracks cgsKitchenMenu
# =============================================================
set -e

ROLE="${1:-}"
if [ -z "$ROLE" ] && [ -f /etc/celtech/role ]; then
    ROLE="$(cat /etc/celtech/role | tr -d '[:space:]')"
fi

case "$ROLE" in
    expo) APP_DIR="/home/druid/cgsKitchenExpo"; SERVICE="druid-expo.service"; LABEL="Expo Board" ;;
    menu) APP_DIR="/home/druid/cgsKitchenMenu"; SERVICE="druid-menu.service"; LABEL="Menu Board" ;;
    *)    echo "ERROR: role must be 'expo' or 'menu' (got '$ROLE')."; exit 1 ;;
esac

LOG_FILE="/home/druid/update.log"
BRANCH="main"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$ROLE] $1" | tee -a "$LOG_FILE"; }

log "-----------------------------------"
log "Starting CGS Kitchen $LABEL update (native)"

if [ ! -d "$APP_DIR/.git" ]; then
    log "ERROR: $APP_DIR is not a git repository. Aborting."
    exit 1
fi

cd "$APP_DIR"

# ---- Wait for network (up to 30s) --------------------------
log "Waiting for network..."
WAIT=0
NETWORK_OK=1
until ping -c 1 -W 2 8.8.8.8 &>/dev/null; do
    WAIT=$((WAIT + 2))
    if [ $WAIT -ge 30 ]; then
        log "WARNING: No network after 30s. Running existing checkout."
        NETWORK_OK=0
        break
    fi
    sleep 2
done

CHANGED=0
if [ $NETWORK_OK -eq 1 ]; then
    log "Network ready after ${WAIT}s. Fetching..."
    git fetch origin "$BRANCH" >> "$LOG_FILE" 2>&1
    LOCAL=$(git rev-parse HEAD)
    REMOTE=$(git rev-parse "origin/$BRANCH")

    if [ "$LOCAL" = "$REMOTE" ]; then
        if [ -n "$(git status --porcelain)" ]; then
            log "Local modifications detected, resetting..."
            git reset --hard "origin/$BRANCH" >> "$LOG_FILE" 2>&1
            CHANGED=1
        fi
        log "Already up to date ($(git rev-parse --short HEAD))."
    else
        log "Update: $(git rev-parse --short HEAD) -> $(git rev-parse --short origin/$BRANCH)"
        git reset --hard "origin/$BRANCH" >> "$LOG_FILE" 2>&1
        CHANGED=1
    fi
fi

# ---- Python deps (only if requirements changed) -------------
# pygame + stdlib is all we need. Installed once at provision time; this
# just heals a missing venv.
if [ ! -d "$APP_DIR/.venv" ]; then
    log "Creating venv and installing deps..."
    python3 -m venv "$APP_DIR/.venv"
    "$APP_DIR/.venv/bin/pip" install --upgrade pip >> "$LOG_FILE" 2>&1
    "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt" >> "$LOG_FILE" 2>&1
    CHANGED=1
elif [ $CHANGED -eq 1 ]; then
    log "Syncing Python deps..."
    "$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt" >> "$LOG_FILE" 2>&1
fi

# ---- Restart the board if anything changed -----------------
if [ $CHANGED -eq 1 ]; then
    log "Restarting $SERVICE..."
    sudo systemctl restart "$SERVICE"
else
    log "No change; leaving $SERVICE running."
fi

log "Update complete."
log "-----------------------------------"
exit 0

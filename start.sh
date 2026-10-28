#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# start.sh - Linux launcher for the Snapgent bridge.
set -u

cd "$(dirname "$0")" || exit 1

BRIDGE_PORT="${ZS_BRIDGE_PORT:-17613}"
LOG_DIR="logs"
LOG_FILE="$LOG_DIR/start.log"
mkdir -p "$LOG_DIR" 2>/dev/null

log() {
    printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" >>"$LOG_FILE" 2>/dev/null || true
}

echo
echo "  === Snapgent Bridge (Linux Launcher) ==="
echo
log "===== start.sh launched ====="

# --- 1. Free previous bridge port if in use --------------------------------
echo "  [1/3] Checking bridge port $BRIDGE_PORT..."
if command -v lsof >/dev/null 2>&1; then
    OLD_PID="$(lsof -ti "tcp:$BRIDGE_PORT" -s TCP:LISTEN 2>/dev/null | head -n1)"
    if [ -n "${OLD_PID:-}" ]; then
        echo "        Killing previous bridge process (pid $OLD_PID)..."
        kill -TERM "$OLD_PID" 2>/dev/null || true
        sleep 1
        if kill -0 "$OLD_PID" 2>/dev/null; then
            kill -9 "$OLD_PID" 2>/dev/null || true
            sleep 1
        fi
    fi
elif command -v fuser >/dev/null 2>&1; then
    fuser -k "${BRIDGE_PORT}/tcp" >/dev/null 2>&1 || true
fi
echo "        Port $BRIDGE_PORT is ready."

# --- 2. Check configuration -----------------------------------------------
echo "  [2/3] Checking config.json..."
if [ ! -f "config.json" ]; then
    echo "        Creating default config.json..."
    cat << 'EOF' > config.json
{
  "mcpServers": {}
}
EOF
fi
echo "        config.json OK."

# --- 3. Determine how to run the bridge ------------------------------------
echo "  [3/3] Locating bridge executable/script..."

if [ -x "./bridge" ]; then
    echo "        Starting native bridge binary..."
    log "Starting native ./bridge"
    ./bridge
elif [ -f "bridge.py" ]; then
    PY=""
    for cand in python3 python; do
        if command -v "$cand" >/dev/null 2>&1; then
            PY="$cand"
            break
        fi
    done
    if [ -z "$PY" ]; then
        echo "  ERROR: python3 not found."
        exit 1
    fi
    echo "        Starting bridge.py using $PY..."
    log "Starting bridge.py using $PY"
    "$PY" bridge.py
elif [ -f "bridge.exe" ]; then
    if command -v wine >/dev/null 2>&1; then
        echo "        Running bridge.exe via Wine..."
        log "Running bridge.exe via Wine"
        wine bridge.exe
    else
        echo
        echo "  Notice: bridge.exe is a Windows binary and 'wine' was not found."
        echo "  To run bridge.exe on Linux, install Wine:"
        echo "      sudo apt install wine"
        echo "  Or run with Wine: wine bridge.exe"
        echo
        exit 1
    fi
else
    echo "  ERROR: Neither ./bridge, bridge.py, nor bridge.exe was found."
    exit 1
fi

BRIDGE_EXIT=$?
log "bridge exited with code $BRIDGE_EXIT"
exit "$BRIDGE_EXIT"

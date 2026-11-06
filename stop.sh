#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# stop.sh - Linux launcher to stop the Snapgent bridge.
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
echo "  === Snapgent Bridge (Linux Stopper) ==="
echo
log "===== stop.sh launched ====="

STOPPED=0

# --- 1. Hentikan systemd user service jika aktif -------------------------
if command -v systemctl >/dev/null 2>&1; then
    if systemctl --user is-active --quiet snapgent-bridge.service 2>/dev/null; then
        echo "  [1/3] Menghentikan service systemd (snapgent-bridge)..."
        systemctl --user stop snapgent-bridge.service 2>/dev/null || true
        STOPPED=1
    else
        echo "  [1/3] Service systemd tidak sedang aktif."
    fi
else
    echo "  [1/3] systemctl tidak tersedia."
fi

# --- 2. Periksa dan hentikan proses di port bridge ----------------------
echo "  [2/3] Memeriksa port bridge $BRIDGE_PORT..."
if command -v lsof >/dev/null 2>&1; then
    OLD_PID="$(lsof -ti "tcp:$BRIDGE_PORT" -s TCP:LISTEN 2>/dev/null | head -n1)"
    if [ -n "${OLD_PID:-}" ]; then
        echo "        Menghentikan proses bridge PID $OLD_PID di port $BRIDGE_PORT..."
        kill -TERM "$OLD_PID" 2>/dev/null || true
        sleep 1
        if kill -0 "$OLD_PID" 2>/dev/null; then
            kill -9 "$OLD_PID" 2>/dev/null || true
        fi
        STOPPED=1
    fi
elif command -v fuser >/dev/null 2>&1; then
    fuser -k "${BRIDGE_PORT}/tcp" >/dev/null 2>&1 && STOPPED=1 || true
fi

# --- 3. Bersihkan proses bridge.py yang tersisa -------------------------
echo "  [3/3] Memeriksa proses bridge.py yang tersisa..."
pkill -f "python.*bridge\.py" 2>/dev/null && STOPPED=1 || true

if [ "$STOPPED" -eq 1 ]; then
    echo
    echo "  [✓] Snapgent Bridge berhasil dihentikan."
    log "Snapgent Bridge stopped successfully via stop.sh"
else
    echo
    echo "  [-] Snapgent Bridge sudah dalam keadaan mati (tidak aktif)."
fi
echo


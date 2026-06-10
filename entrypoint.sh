#!/bin/bash
set -e

# Clean up stale lock files left by a previous container stop (non-clean shutdown)
rm -f /tmp/.X1-lock /tmp/.X11-unix/X1 2>/dev/null || true

# Virtual framebuffer — Firefox renders here
Xvfb :1 -screen 0 1280x900x24 -nolisten tcp &
export DISPLAY=:1
sleep 2  # give Xvfb time to initialise

# Minimal window manager (Firefox needs one for chrome/decorations)
fluxbox -display :1 &>/dev/null &

# VNC server — no password, LAN/Docker use only
x11vnc -display :1 -nopw -listen 0.0.0.0 -xkb -forever -shared -quiet &

# noVNC web UI on port 6080 — open http://<host>:6080 to see the browser
websockify --web=/opt/novnc 6080 localhost:5900 &

exec python /app/kudos.py

FROM python:3.12-slim

# System packages: virtual display, VNC, window manager, noVNC downloader
RUN apt-get update && apt-get install -y --no-install-recommends \
        xvfb \
        x11vnc \
        xauth \
        fluxbox \
        wget \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# noVNC (web-based VNC viewer) + websockify (WebSocket-to-TCP proxy)
RUN wget -qO /tmp/novnc.tar.gz \
        https://github.com/novnc/noVNC/archive/refs/tags/v1.5.0.tar.gz \
    && tar -xzf /tmp/novnc.tar.gz -C /opt \
    && mv /opt/noVNC-1.5.0 /opt/novnc \
    && ln -s /opt/novnc/vnc.html /opt/novnc/index.html \
    && rm /tmp/novnc.tar.gz

RUN pip install --no-cache-dir websockify

# Python dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Firefox binary + all its system library dependencies
RUN playwright install firefox && playwright install-deps firefox

COPY *.py .

VOLUME ["/data"]

# noVNC web UI
EXPOSE 6080

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]

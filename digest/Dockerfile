FROM python:3.12-slim

# Install supercronic (auto-detect architecture)
ARG TARGETARCH
RUN apt-get update && apt-get install -y curl && \
    SUPERCRONIC_ARCH=$(case "${TARGETARCH}" in arm64) echo "linux-arm64" ;; *) echo "linux-amd64" ;; esac) && \
    curl -fsSL "https://github.com/aptible/supercronic/releases/download/v0.2.33/supercronic-${SUPERCRONIC_ARCH}" \
      -o /usr/local/bin/supercronic && \
    chmod +x /usr/local/bin/supercronic && \
    apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["supercronic", "-no-reap", "/app/crontab"]

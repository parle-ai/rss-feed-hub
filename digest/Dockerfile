FROM python:3.12-slim

# Install supercronic
ARG SUPERCRONIC_URL=https://github.com/aptible/supercronic/releases/download/v0.2.33/supercronic-linux-amd64
ARG SUPERCRONIC_SHA=71b0d58cc53f6bd72cf2f293e09e294b79c666d8
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL "${SUPERCRONIC_URL}" -o /usr/local/bin/supercronic && \
    echo "${SUPERCRONIC_SHA}  /usr/local/bin/supercronic" | sha1sum -c - && \
    chmod +x /usr/local/bin/supercronic && \
    apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["supercronic", "/app/crontab"]

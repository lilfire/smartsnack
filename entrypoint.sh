#!/bin/bash
set -e

# The container starts as root so we can fix ownership of the mounted /data
# named volume — Docker leaves a pre-existing volume owned by root even though
# the image chowns /data at build time. Chown, then re-exec this script as the
# unprivileged appuser (via gosu, which forwards signals for clean shutdown).
if [ "$(id -u)" = "0" ]; then
  chown -R appuser:appuser /data /app/certs
  exec gosu appuser "$0" "$@"
fi

# ---- from here on, running as appuser ----

# Generate self-signed cert if not present
if [ ! -f /app/certs/cert.pem ]; then
  echo "Generating self-signed SSL certificate..."
  mkdir -p /app/certs
  openssl req -x509 -newkey rsa:2048 \
    -keyout /app/certs/key.pem \
    -out /app/certs/cert.pem \
    -days 365 -nodes \
    -subj "/CN=smartsnack" 2>/dev/null
  echo "Certificate generated."
fi

echo "Starting SmartSnack on HTTP :5001..."
gunicorn \
  --bind 0.0.0.0:5001 \
  --workers 2 \
  --threads 2 \
  --timeout 120 \
  --graceful-timeout 30 \
  --worker-tmp-dir /dev/shm \
  --log-level info \
  app:app &

echo "Starting SmartSnack on HTTPS :5000..."
exec gunicorn \
  --bind 0.0.0.0:5000 \
  --workers 2 \
  --threads 2 \
  --timeout 120 \
  --graceful-timeout 30 \
  --worker-tmp-dir /dev/shm \
  --certfile /app/certs/cert.pem \
  --keyfile /app/certs/key.pem \
  --log-level info \
  app:app

# syntax=docker/dockerfile:1
# ---------- builder ----------
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --prefix=/install \
        torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install --prefix=/install -r requirements.txt \
    && ( \
       find /install -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null; \
       find /install -type d -name 'tests' -exec rm -rf {} + 2>/dev/null; \
       find /install -type d -name 'test' -exec rm -rf {} + 2>/dev/null; \
       find /install -name '*.pyc' -delete 2>/dev/null; \
       find /install -name '*.pyi' -delete 2>/dev/null; \
       rm -rf /install/lib/python3.12/site-packages/torch/test \
              /install/lib/python3.12/site-packages/torch/include \
              /install/lib/python3.12/site-packages/torch/share \
              /install/lib/python3.12/site-packages/torchvision/datasets \
              /install/lib/python3.12/site-packages/caffe2 \
    ) || true

# ---------- runtime ----------
FROM python:3.12-slim

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    openssl gosu tesseract-ocr tesseract-ocr-nor tesseract-ocr-eng

WORKDIR /app

COPY --from=builder /install /usr/local

COPY app.py .
COPY config.py .
COPY exceptions.py .
COPY extensions.py .
COPY db.py .
COPY helpers.py .
COPY translations.py .
COPY migrations.py .
COPY services/ services/
COPY blueprints/ blueprints/
COPY templates/ templates/
COPY translations/ translations/
COPY static/ static/
COPY entrypoint.sh .
RUN sed -i 's/\r$//' entrypoint.sh && chmod +x entrypoint.sh

RUN mkdir -p /data /app/certs

# Create non-root user and hand over app + data dirs so the runtime process
# (and any RCE in the image pipeline) does not run as root. UID 1000 keeps
# the named /data volume writable across container rebuilds.
RUN groupadd --system --gid 1000 appuser \
    && useradd --system --uid 1000 --gid 1000 --home-dir /app --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app /data

ENV DB_PATH=/data/smartsnack.sqlite

EXPOSE 5000

# NOTE: We intentionally do NOT set `USER appuser` here. The container starts as
# root so the entrypoint can chown the mounted /data named volume (which Docker
# leaves root-owned when it pre-exists an image rebuild), then drops privileges
# to appuser via gosu before starting gunicorn. The server processes still run
# unprivileged; only the brief pre-flight chown runs as root.
ENTRYPOINT ["/app/entrypoint.sh"]

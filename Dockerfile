# syntax=docker/dockerfile:1
# ---------- builder ----------
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --prefix=/install -r requirements.txt

# ---------- runtime ----------
FROM python:3.12-slim

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    openssl libglib2.0-0 \
    tesseract-ocr tesseract-ocr-nor tesseract-ocr-eng

WORKDIR /app

COPY --from=builder /install /usr/local

COPY app.py .
COPY config.py .
COPY exceptions.py .
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

ENV DB_PATH=/data/smartsnack.sqlite

EXPOSE 5000

ENTRYPOINT ["/app/entrypoint.sh"]

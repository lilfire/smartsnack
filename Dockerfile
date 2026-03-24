# ---------- builder ----------
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .

RUN pip install --no-cache-dir --prefix=/install \
        torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt \
    && find /install -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null; \
       find /install -type d -name 'tests' -exec rm -rf {} + 2>/dev/null; \
       find /install -type d -name 'test' -exec rm -rf {} + 2>/dev/null; \
       find /install -name '*.pyc' -delete 2>/dev/null; \
       find /install -name '*.pyi' -delete 2>/dev/null; \
       rm -rf /install/lib/python3.12/site-packages/torch/test \
              /install/lib/python3.12/site-packages/torch/include \
              /install/lib/python3.12/site-packages/torch/share \
              /install/lib/python3.12/site-packages/torchvision/datasets \
              /install/lib/python3.12/site-packages/caffe2 \
    || true

# ---------- runtime ----------
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    openssl libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

ENV EASYOCR_MODULE_PATH=/data/.easyocr

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

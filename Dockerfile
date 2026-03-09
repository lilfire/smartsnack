FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends openssl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY config.py .
copy exceptions.py .
COPY db.py .
COPY helpers.py .
COPY translations.py .
COPY migrations.py .
COPY exceptions.py .
COPY services/ services/
COPY blueprints/ blueprints/
COPY templates/ templates/
COPY translations/ translations/
COPY static/ static/
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

RUN mkdir -p /data /app/certs

ENV DB_PATH=/data/smartsnack.sqlite

EXPOSE 5000

ENTRYPOINT ["/app/entrypoint.sh"]
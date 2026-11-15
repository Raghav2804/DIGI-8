FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies in their own layer so source changes do not invalidate
# the package-install cache.
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --timeout=300 --retries=10 -r requirements.txt

# Copy only runtime files. The SQLite database is created in a persistent
# Compose volume at runtime; local database files and caches are not baked in.
COPY --chown=10001:10001 app.py config.py ./
COPY --chown=10001:10001 database/ ./database/
COPY --chown=10001:10001 models/ ./models/
COPY --chown=10001:10001 routes/ ./routes/
COPY --chown=10001:10001 services/ ./services/
COPY --chown=10001:10001 static/ ./static/
COPY --chown=10001:10001 templates/ ./templates/
COPY --chown=10001:10001 dataset/ ./dataset/

RUN mkdir -p /data && chown -R 10001:10001 /data

USER 10001:10001

EXPOSE 5000

CMD ["gunicorn", "--workers=2", "--threads=4", "--bind=0.0.0.0:5000", "--timeout=180", "--access-logfile=-", "--error-logfile=-", "--preload", "app:app"]

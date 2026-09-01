# Container image for TRINETRA. Works on Fly.io, Cloud Run, Koyeb, or any
# container host. The platform needs no external service by default.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/backend:/app/database:/app/ai:/app/graph \
    PORT=8000

WORKDIR /app

# Dependencies first, so a source change does not invalidate the layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/   ./backend/
COPY frontend/  ./frontend/
COPY ai/        ./ai/
COPY graph/     ./graph/
COPY database/  ./database/

# Run as a non-root user.
RUN useradd --create-home --uid 10001 trinetra \
    && mkdir -p /app/uploads /app/data \
    && chown -R trinetra:trinetra /app
USER trinetra

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health').status==200 else 1)"

CMD ["sh", "-c", "uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port ${PORT}"]

# Slim API image (finalized in Phase 19 / 23)
FROM python:3.11-slim
WORKDIR /srv
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt
COPY api/ api/
COPY src/ src/
COPY params.yaml .
COPY models/ models/
RUN useradd -m appuser && chown -R appuser /srv
USER appuser
ENV PORT=8000
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]

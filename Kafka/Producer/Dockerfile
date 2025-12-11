# Kafka/Producer/Dockerfile
FROM python:3.11-slim

# Avoid Python creating .pyc files and enable unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false

# Create non-root user
RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /app

# Install minimal OS deps (tzdata for timezone and build-essential only if needed)
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends tzdata ca-certificates git curl && \
    rm -rf /var/lib/apt/lists/*

# Copy and install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and set permissions
COPY --chown=app:app . .

USER app

# Optional: small healthcheck script (adjust path if needed)
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import sys,os,socket; sys.exit(0)" || exit 1

# Default command — adjust if your actual entrypoint differs
CMD ["python", "src/main.py"]

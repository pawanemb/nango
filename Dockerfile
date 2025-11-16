# ---------------------------------------------------------
# 1) Builder Stage (build wheels, install deps safely)
# ---------------------------------------------------------
FROM python:3.10-slim AS builder

WORKDIR /app

# Install system deps ONLY required for building wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Build wheels instead of installing directly (faster runtime)
RUN pip install --upgrade pip && \
    pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# ---------------------------------------------------------
# 2) Runtime Stage (clean, small, fast)
# ---------------------------------------------------------
FROM python:3.10-slim

WORKDIR /app

# Install only minimal system libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy prebuilt wheels (super fast install)
COPY --from=builder /wheels /wheels
COPY requirements.txt .

RUN pip install --no-cache-dir /wheels/*

# Copy application code
COPY . .

# Expose FastAPI port
EXPOSE 8000

# ---------------------------------------------------------
# Gunicorn + Uvicorn Workers (optimized)
# ---------------------------------------------------------
ENV WORKERS=4
ENV THREADS=1
ENV TIMEOUT=60

CMD ["gunicorn", "main:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "-w", "4", \
     "--threads", "1", \
     "--keep-alive", "120", \
     "-b", "0.0.0.0:8000"]

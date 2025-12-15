# ============================================
# Arab Dubbing API - Production Dockerfile
# Optimized for Docker Layer Caching
# ============================================

# Use slim Python image for smaller size
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set working directory
WORKDIR /app

# ============================================
# LAYER CACHING STRATEGY (CRITICAL!)
# Copy requirements first, then install
# This way, pip install is cached unless requirements.txt changes
# ============================================

# Step 1: Copy only requirements first
COPY requirements.txt .

# Step 2: Install Python dependencies (CACHED if requirements unchanged)
RUN pip install --no-cache-dir -r requirements.txt

# Step 3: Copy application code (AFTER pip install)
COPY . .

# Create directories for media files
RUN mkdir -p audio output uploads

# Expose port (Render uses 10000)
EXPOSE 10000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:10000/health || exit 1

# Run with Gunicorn + Uvicorn workers
# --timeout 600: Long timeout for video processing
# -k uvicorn.workers.UvicornH11Worker: Async worker for FastAPI
CMD ["gunicorn", "main:app", "-k", "uvicorn.workers.UvicornH11Worker", "--bind", "0.0.0.0:10000", "--timeout", "600", "--workers", "1"]

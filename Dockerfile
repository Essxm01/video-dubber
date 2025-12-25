# ============================================
# Arab Dubbing API - Root Dockerfile (Restored)
# Base: python:3.9-slim as requested
# ============================================

FROM python:3.9-slim

# Set environment system variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements from backend folder
COPY backend/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application code to root of container
COPY backend/ .

# Create directories for media if needed
RUN mkdir -p audio output uploads

# Expose port 10000
EXPOSE 10000

# Run FastAPI with Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]

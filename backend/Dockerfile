FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python deps first for better layer caching.
COPY backend/requirements.txt /app/backend/requirements.txt
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt -r /app/requirements.txt

# Copy full project because backend imports backend.pipeline and other root modules.
COPY . /app

ENV BACKEND_PORT=48721 \
    NO_RELOAD=1 \
    CUSTOM_COMPONENTS_DIR=/app/backend/custom_components

EXPOSE 48721

CMD ["python", "run_backend.py"]

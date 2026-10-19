FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY sandbox_service ./sandbox_service
COPY tests ./tests
COPY scripts ./scripts
COPY docs ./docs
COPY README.md ./
COPY .env.example ./

# This image runs the local demonstration; it is not an HTTP web service.
CMD ["python", "scripts/run_live_demo.py"]

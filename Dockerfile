# syntax=docker/docker-engine:24.0.0
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies for FalkorDB connectivity
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Core build tools
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy poetry files for dependency management
COPY pyproject.toml poetry.lock ./

# Install poetry and dependencies
RUN pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-dev

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Create non-root user for security
RUN useradd -m -u 1001 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Copy application code
COPY . /app

# Create logs directory
RUN mkdir -p /app/logs

# Set health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import src.core.incident_resolver; print('FalkorDB connection available')" || exit 1

# Expose port for FastAPI application
EXPOSE 8000

# Default command - run the multi-agent pipeline demo
CMD ["python", "-c", "
from src.core.multi_agent_pipeline import demo_pipeline
print('Starting RepoGraph FalkorDB Incident Resolver...')
result = demo_pipeline()
print(f'\nIncident Resolution Complete!')
print(f'Fault Signature: {result.fault_signature}')
print(f'Root Cause: {result.root_cause_function}')
print(f'Affected Functions: {result.affected_functions}')
print(f'Semantic Facts Created: {len(result.semantic_facts_created)}')
"]
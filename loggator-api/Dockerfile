FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps from pyproject.toml
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    aiosmtplib alembic apscheduler asyncpg boto3 fastapi httpx \
    "opensearch-py[async]" pgvector pydantic-settings requests-aws4auth \
    slowapi "sqlalchemy[asyncio]" structlog tiktoken typer "uvicorn[standard]" \
    "langchain-core>=0.3" "langchain-ollama>=0.3" "langchain-anthropic>=0.3" "langchain-openai>=0.3"

COPY . .

RUN sed -i 's/\r//' /app/docker-entrypoint.sh && chmod +x /app/docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]

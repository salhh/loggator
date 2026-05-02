"""Seed fake logs into OpenSearch for local testing.

Uses the same env vars as the API (OPENSEARCH_HOST, OPENSEARCH_PORT, etc.).
From Docker stack: docker compose -f docker-compose.local.yml exec api python scripts/seed_logs.py
"""
import asyncio
import os
import random
from datetime import datetime, timedelta, timezone

from opensearchpy import AsyncOpenSearch


def _env_bool(key: str, default: bool) -> bool:
    v = os.environ.get(key)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes")


INDEX = os.environ.get("LOG_SEED_INDEX", "logs-app-local")
OS_HOST = os.environ.get("OPENSEARCH_HOST", "localhost")
OS_PORT = int(os.environ.get("OPENSEARCH_PORT", "9200"))
OS_USE_SSL = _env_bool("OPENSEARCH_USE_SSL", False)
OS_VERIFY = _env_bool("OPENSEARCH_VERIFY_CERTS", True)

SERVICES = ["auth-service", "payment-service", "api-gateway", "user-service", "notification-service"]
LEVELS = ["INFO", "INFO", "INFO", "INFO", "WARN", "ERROR", "ERROR", "DEBUG"]
MESSAGES = [
    "Request processed successfully",
    "Database query completed in {ms}ms",
    "Cache miss for key user:{id}",
    "User {id} authenticated",
    "Connection pool exhausted, retrying...",
    "Unhandled exception in request handler",
    "NullPointerException at PaymentProcessor.java:142",
    "Timeout waiting for upstream response after 30s",
    "Disk usage at 87%, approaching threshold",
    "Failed to connect to Redis after 3 retries",
    "Memory usage spike detected: 94%",
    "SQL query took 8423ms — possible N+1 issue",
]

async def seed():
    client = AsyncOpenSearch(
        hosts=[{"host": OS_HOST, "port": OS_PORT}],
        use_ssl=OS_USE_SSL,
        verify_certs=OS_VERIFY,
    )

    # Create index
    if not await client.indices.exists(index=INDEX):
        await client.indices.create(index=INDEX, body={
            "mappings": {"properties": {"@timestamp": {"type": "date"}}}
        })
        print(f"Created index: {INDEX}")

    now = datetime.now(timezone.utc)
    bulk_body = []

    for i in range(200):
        ts = now - timedelta(minutes=random.randint(0, 60))
        level = random.choice(LEVELS)
        msg = random.choice(MESSAGES).format(ms=random.randint(1, 5000), id=random.randint(100, 999))
        service = random.choice(SERVICES)

        bulk_body.append({"index": {"_index": INDEX}})
        bulk_body.append({
            "@timestamp": ts.isoformat(),
            "level": level,
            "message": msg,
            "service": service,
            "host": f"node-{random.randint(1, 5)}",
            "environment": "production",
            "trace_id": f"trace-{random.randint(10000, 99999)}",
            "duration_ms": random.randint(1, 10000) if "Request" in msg else None,
        })

    resp = await client.bulk(body=bulk_body, refresh=True)
    errors = [i for i in resp["items"] if "error" in i.get("index", {})]
    n_docs = len(bulk_body) // 2
    ok = n_docs - len(errors)
    print(f"Seeded {ok} logs into {INDEX} at {OS_HOST}:{OS_PORT} ({len(errors)} errors)")
    await client.close()


if __name__ == "__main__":
    asyncio.run(seed())

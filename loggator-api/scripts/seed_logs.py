"""Seed fake logs into OpenSearch for local testing."""
import asyncio
import random
from datetime import datetime, timedelta, timezone

from opensearchpy import AsyncOpenSearch

INDEX = "logs-app-2024.01"

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
    client = AsyncOpenSearch(hosts=[{"host": "localhost", "port": 9200}], use_ssl=False, verify_certs=False)

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
            "trace_id": f"trace-{random.randint(10000, 99999)}",
            "duration_ms": random.randint(1, 10000) if "Request" in msg else None,
        })

    resp = await client.bulk(body=bulk_body, refresh=True)
    errors = [i for i in resp["items"] if "error" in i.get("index", {})]
    print(f"Seeded {200 - len(errors)} logs into {INDEX}  ({len(errors)} errors)")
    await client.close()


if __name__ == "__main__":
    asyncio.run(seed())

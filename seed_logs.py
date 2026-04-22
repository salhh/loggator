"""
Seed realistic error logs into OpenSearch to test the Loggator alerting flow.
Run with: python seed_logs.py
Requires: pip install opensearch-py
"""
import json
import random
import uuid
from datetime import datetime, timedelta, timezone

from opensearchpy import OpenSearch

OS_HOST = "localhost"
OS_PORT = 9200
INDEX = "logs-app-2026.04.21"

client = OpenSearch(
    hosts=[{"host": OS_HOST, "port": OS_PORT}],
    http_compress=True,
    use_ssl=False,
    verify_certs=False,
)

SERVICES = [
    "auth-service",
    "payment-service",
    "api-gateway",
    "user-service",
    "notification-service",
    "order-service",
]

PODS = {s: f"{s}-{uuid.uuid4().hex[:5]}" for s in SERVICES}

ERROR_TEMPLATES = [
    ("ERROR", "Connection pool exhausted: max 10 connections reached for postgresql://db:5432/prod"),
    ("ERROR", "NullPointerException at com.example.OrderService.processOrder(OrderService.java:142)"),
    ("ERROR", "Redis connection refused: [Errno 111] Connection refused to redis:6379"),
    ("ERROR", "HTTP 503 Service Unavailable from downstream payment-gateway after 30s timeout"),
    ("ERROR", "OOMKilled: container exceeded memory limit of 512Mi, restarting pod"),
    ("ERROR", "Database deadlock detected on table `orders` — transaction rolled back"),
    ("ERROR", "JWT signature verification failed: token has been tampered"),
    ("ERROR", "Disk usage at 94% on /var/data — writes may fail"),
    ("ERROR", "Circuit breaker OPEN for inventory-service after 5 consecutive failures"),
    ("ERROR", "SSL certificate for api.example.com expires in 3 days"),
    ("WARN",  "Response time 4.2s exceeds SLA threshold of 2s for POST /api/v1/checkout"),
    ("WARN",  "Retry attempt 3/5 for message queue consumer group loggator-alerts"),
    ("WARN",  "Memory usage at 87% — GC pressure increasing on auth-service"),
    ("WARN",  "Rate limit approaching: 4800/5000 requests used in last 60s"),
    ("WARN",  "Stale cache detected: last refresh 18 minutes ago, TTL is 15 minutes"),
    ("INFO",  "User login failed: invalid credentials for user admin@example.com (attempt 4)"),
    ("INFO",  "Pod restart detected: payment-service restarted 3 times in last 10 minutes"),
    ("INFO",  "Scheduled job `cleanup-expired-sessions` failed to complete within 60s timeout"),
]

NOISE = [
    ("INFO",  "GET /health 200 OK 2ms"),
    ("INFO",  "GET /metrics 200 OK 1ms"),
    ("DEBUG", "Cache hit for key user:session:abc123"),
    ("INFO",  "heartbeat ping received"),
]


def make_doc(level: str, message: str, service: str, dt: datetime) -> dict:
    return {
        "@timestamp": dt.isoformat(),
        "level": level,
        "message": message,
        "service": service,
        "host": PODS[service],
        "environment": "production",
        "trace_id": uuid.uuid4().hex[:16],
    }


def bulk_index(docs: list[dict]):
    body = []
    for doc in docs:
        body.append({"index": {"_index": INDEX, "_id": str(uuid.uuid4())}})
        body.append(doc)
    resp = client.bulk(body=body)
    errors = [i for i in resp["items"] if "error" in i.get("index", {})]
    print(f"  Indexed {len(docs) - len(errors)} docs, {len(errors)} errors")


def seed():
    now = datetime.now(timezone.utc)
    docs = []

    print(f"Seeding logs into {INDEX} ...")

    # ── Spike: last 10 minutes — dense error burst (triggers anomaly + alert) ──
    print("  [1/3] Injecting error spike (last 10 min)...")
    for i in range(120):
        dt = now - timedelta(seconds=random.randint(0, 600))
        level, msg = random.choice(ERROR_TEMPLATES[:10])  # heavy errors only
        service = random.choice(SERVICES[:3])             # blame first 3 services
        docs.append(make_doc(level, msg, service, dt))

    # ── Background: last 2 hours — mixed warn/error/info ──
    print("  [2/3] Injecting background activity (last 2 hours)...")
    for i in range(200):
        dt = now - timedelta(minutes=random.randint(11, 120))
        level, msg = random.choice(ERROR_TEMPLATES)
        service = random.choice(SERVICES)
        docs.append(make_doc(level, msg, service, dt))

    # ── Noise: health checks / debug (should be filtered by preprocessor) ──
    print("  [3/3] Injecting noise logs (should be filtered)...")
    for i in range(50):
        dt = now - timedelta(seconds=random.randint(0, 3600))
        level, msg = random.choice(NOISE)
        service = random.choice(SERVICES)
        docs.append(make_doc(level, msg, service, dt))

    random.shuffle(docs)
    bulk_index(docs)

    print(f"\nDone — {len(docs)} documents seeded into '{INDEX}'")
    print("\nWhat to expect:")
    print("  • Streaming worker picks up new docs within ~10s")
    print("  • Anomaly detected → Slack alert fires")
    print("  • Check /anomalies and /alerts pages")
    print("  • Dashboard auto-analysis will show the spike")


if __name__ == "__main__":
    seed()

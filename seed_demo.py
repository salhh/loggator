"""
Full demo seed script — populates OpenSearch + PostgreSQL with realistic data.
Run via:  docker exec -i loving-pascal-f44d63-api-1 python /tmp/seed_demo.py
"""
import asyncio
import json
import random
import uuid
from datetime import datetime, timedelta, timezone

# ── OpenSearch ────────────────────────────────────────────────────────────────
from opensearchpy import OpenSearch

OS_HOST = "opensearch"
OS_PORT = 9200

os_client = OpenSearch(
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
    "inventory-service",
    "analytics-service",
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
    ("ERROR", "Unhandled exception in payment processor: card declined with code 51"),
    ("ERROR", "Kafka consumer lag exceeded threshold: 150000 messages behind on topic orders"),
    ("ERROR", "S3 upload failed: AccessDenied for bucket prod-user-uploads after 3 retries"),
    ("WARN",  "Response time 4.2s exceeds SLA threshold of 2s for POST /api/v1/checkout"),
    ("WARN",  "Retry attempt 3/5 for message queue consumer group loggator-alerts"),
    ("WARN",  "Memory usage at 87% — GC pressure increasing on auth-service"),
    ("WARN",  "Rate limit approaching: 4800/5000 requests used in last 60s"),
    ("WARN",  "Stale cache detected: last refresh 18 minutes ago, TTL is 15 minutes"),
    ("WARN",  "Slow query detected (2340ms): SELECT * FROM orders WHERE user_id = ? AND status = ?"),
    ("WARN",  "TLS handshake timeout after 5s connecting to external-api.partner.com"),
    ("INFO",  "User login failed: invalid credentials for user admin@example.com (attempt 4)"),
    ("INFO",  "Pod restart detected: payment-service restarted 3 times in last 10 minutes"),
    ("INFO",  "Scheduled job `cleanup-expired-sessions` failed to complete within 60s timeout"),
]

NOISE = [
    ("INFO",  "GET /health 200 OK 2ms"),
    ("INFO",  "GET /metrics 200 OK 1ms"),
    ("DEBUG", "Cache hit for key user:session:abc123"),
    ("INFO",  "heartbeat ping received"),
    ("DEBUG", "Connection returned to pool"),
    ("INFO",  "POST /api/v1/events 202 Accepted 8ms"),
]


def make_log(level: str, message: str, service: str, dt: datetime) -> dict:
    return {
        "@timestamp": dt.isoformat(),
        "level": level,
        "message": message,
        "service": service,
        "host": PODS[service],
        "environment": "production",
        "trace_id": uuid.uuid4().hex[:16],
    }


def bulk_os(docs: list[dict], index: str):
    body = []
    for doc in docs:
        body.append({"index": {"_index": index, "_id": str(uuid.uuid4())}})
        body.append(doc)
    resp = os_client.bulk(body=body)
    errors = [i for i in resp["items"] if "error" in i.get("index", {})]
    print(f"  → OpenSearch [{index}]: {len(docs) - len(errors)} indexed, {len(errors)} errors")


def seed_opensearch(now: datetime):
    print("\n[1/2] Seeding OpenSearch logs ...")

    for days_ago in range(6, -1, -1):
        day = now - timedelta(days=days_ago)
        index = f"logs-app-{day.strftime('%Y.%m.%d')}"
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)

        docs = []

        if days_ago == 0:
            # Today: dense error spike in last 15 min + background
            for _ in range(150):
                dt = now - timedelta(seconds=random.randint(0, 900))
                level, msg = random.choice(ERROR_TEMPLATES[:10])
                service = random.choice(SERVICES[:3])
                docs.append(make_log(level, msg, service, dt))

            for _ in range(300):
                dt = now - timedelta(minutes=random.randint(15, 480))
                level, msg = random.choice(ERROR_TEMPLATES)
                service = random.choice(SERVICES)
                docs.append(make_log(level, msg, service, dt))

            for _ in range(80):
                dt = now - timedelta(seconds=random.randint(0, 86400))
                level, msg = random.choice(NOISE)
                service = random.choice(SERVICES)
                docs.append(make_log(level, msg, service, dt))

        elif days_ago == 2:
            # Two days ago: moderate incident mid-day
            for _ in range(80):
                base = day_start + timedelta(hours=14)
                dt = base + timedelta(minutes=random.randint(0, 45))
                level, msg = random.choice(ERROR_TEMPLATES)
                service = random.choice(SERVICES[2:5])
                docs.append(make_log(level, msg, service, dt))

            for _ in range(200):
                dt = day_start + timedelta(seconds=random.randint(0, 86400))
                level, msg = random.choice(ERROR_TEMPLATES[-8:])
                service = random.choice(SERVICES)
                docs.append(make_log(level, msg, service, dt))

            for _ in range(60):
                dt = day_start + timedelta(seconds=random.randint(0, 86400))
                level, msg = random.choice(NOISE)
                service = random.choice(SERVICES)
                docs.append(make_log(level, msg, service, dt))

        else:
            # Other days: normal background noise
            for _ in range(150):
                dt = day_start + timedelta(seconds=random.randint(0, 86400))
                level, msg = random.choice(ERROR_TEMPLATES[-10:])
                service = random.choice(SERVICES)
                docs.append(make_log(level, msg, service, dt))

            for _ in range(50):
                dt = day_start + timedelta(seconds=random.randint(0, 86400))
                level, msg = random.choice(NOISE)
                service = random.choice(SERVICES)
                docs.append(make_log(level, msg, service, dt))

        random.shuffle(docs)
        bulk_os(docs, index)


# ── PostgreSQL ────────────────────────────────────────────────────────────────
import asyncpg


async def seed_postgres(now: datetime):
    print("\n[2/2] Seeding PostgreSQL ...")

    conn = await asyncpg.connect(
        "postgresql://loggator:loggator@postgres:5432/loggator"
    )

    # ── Summaries ─────────────────────────────────────────────────────────────
    print("  Inserting summaries ...")
    summaries = []
    for i in range(8):
        window_end = now - timedelta(hours=i * 2)
        window_start = window_end - timedelta(hours=2)
        day_index = f"logs-app-{window_end.strftime('%Y.%m.%d')}"
        error_count = random.randint(20, 150)
        top_issues = random.sample([
            "Connection pool exhaustion on payment-service",
            "JWT verification failures on auth-service",
            "Redis unavailability causing cache misses",
            "Memory pressure on order-service pods",
            "Database deadlocks on orders table",
            "Circuit breaker open for inventory-service",
            "Kafka consumer lag building up",
            "SSL certificate near expiry",
        ], k=3)
        summaries.append((
            str(uuid.uuid4()),
            window_start, window_end, day_index,
            f"Detected {error_count} error-level events across {random.randint(3,6)} services. "
            f"Primary issues: {', '.join(top_issues[:2])}. "
            f"Recommend immediate investigation of {random.choice(SERVICES[:4])}.",
            json.dumps(top_issues),
            error_count,
            f"Increase connection pool limits and add circuit breaker for {random.choice(SERVICES)}.",
            "claude-sonnet-4-6",
            random.randint(800, 3200),
        ))

    await conn.executemany("""
        INSERT INTO summaries (id, window_start, window_end, index_pattern, summary,
            top_issues, error_count, recommendation, model_used, tokens_used)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
        ON CONFLICT DO NOTHING
    """, summaries)
    print(f"    → {len(summaries)} summaries")

    # ── Anomalies ─────────────────────────────────────────────────────────────
    print("  Inserting anomalies ...")
    anomaly_templates = [
        ("high", "Coordinated authentication failures across auth-service: 47 failed logins in 8 minutes from 12 distinct IPs, suggesting credential stuffing attack.",
         ["Potential brute-force / credential stuffing attack", "Rate limiting not engaged", "No MFA enforcement detected"],
         ["TA0001 - Initial Access", "T1110.004 - Credential Stuffing"],
         [{"@timestamp": (now - timedelta(minutes=5)).isoformat(), "level": "ERROR", "message": "JWT signature verification failed: token has been tampered", "service": "auth-service"}]),
        ("high", "Payment service connection pool exhausted causing cascade failures: 100% of checkout requests failing, downstream order-service circuit breaker opened.",
         ["Connection pool limit too low for peak traffic", "No backpressure mechanism", "Missing horizontal pod autoscaling"],
         [],
         [{"@timestamp": (now - timedelta(minutes=3)).isoformat(), "level": "ERROR", "message": "Connection pool exhausted: max 10 connections reached", "service": "payment-service"}]),
        ("medium", "Memory pressure spike on order-service: RSS at 94% of 512Mi limit, GC pauses >500ms, response times degrading.",
         ["Memory leak in order processing loop", "Insufficient pod memory limits", "Large object retention in cache"],
         [],
         [{"@timestamp": (now - timedelta(minutes=12)).isoformat(), "level": "WARN", "message": "Memory usage at 87% — GC pressure increasing", "service": "order-service"}]),
        ("medium", "Kafka consumer lag on topic `orders` reached 150k messages — notification-service falling behind, order confirmations delayed.",
         ["Consumer group throughput insufficient", "Downstream notification API rate limited", "Topic partition count too low"],
         [],
         [{"@timestamp": (now - timedelta(minutes=20)).isoformat(), "level": "ERROR", "message": "Kafka consumer lag exceeded threshold: 150000 messages", "service": "notification-service"}]),
        ("high", "S3 AccessDenied errors on prod-user-uploads: IAM role policy may have been inadvertently revoked, user uploads failing.",
         ["IAM policy change or rotation issue", "Possible permissions misconfiguration after deploy", "No fallback storage path"],
         ["TA0005 - Defense Evasion", "T1562.007 - Disable or Modify Cloud Logs"],
         [{"@timestamp": (now - timedelta(minutes=8)).isoformat(), "level": "ERROR", "message": "S3 upload failed: AccessDenied for bucket prod-user-uploads", "service": "api-gateway"}]),
        ("low", "SSL certificate for api.example.com expires in 3 days — no auto-renewal configured.",
         ["Missing cert-manager renewal job", "Manual certificate management in place"],
         [],
         [{"@timestamp": (now - timedelta(hours=2)).isoformat(), "level": "ERROR", "message": "SSL certificate for api.example.com expires in 3 days", "service": "api-gateway"}]),
        ("medium", "Database deadlocks on `orders` table detected 6 times in 30 minutes — transactions being rolled back silently.",
         ["Missing row-level locking strategy", "Long-running transactions holding locks", "Index missing on orders.status column"],
         [],
         [{"@timestamp": (now - timedelta(hours=1)).isoformat(), "level": "ERROR", "message": "Database deadlock detected on table `orders` — transaction rolled back", "service": "order-service"}]),
        ("high", "Redis unavailable — all services falling back to database reads, DB CPU at 95%, response times 10x normal.",
         ["Redis pod OOMKilled and not rescheduled", "No Redis replica or sentinel configured", "Missing graceful degradation"],
         [],
         [{"@timestamp": (now - timedelta(hours=3)).isoformat(), "level": "ERROR", "message": "Redis connection refused: [Errno 111] Connection refused to redis:6379", "service": "user-service"}]),
    ]

    anomaly_ids = []
    anomaly_rows = []
    for i, (severity, summary, hints, mitre, raw_logs) in enumerate(anomaly_templates):
        aid = str(uuid.uuid4())
        anomaly_ids.append(aid)
        detected_at = now - timedelta(minutes=random.randint(2, 180))
        day_index = f"logs-app-{detected_at.strftime('%Y.%m.%d')}"
        anomaly_rows.append((
            aid,
            detected_at,
            detected_at - timedelta(seconds=random.randint(10, 120)),
            day_index,
            severity,
            summary,
            json.dumps(hints),
            json.dumps(mitre),
            json.dumps(raw_logs),
            "claude-sonnet-4-6",
            i < 5,  # first 5 are alerted
        ))

    await conn.executemany("""
        INSERT INTO anomalies (id, detected_at, log_timestamp, index_pattern,
            severity, summary, root_cause_hints, mitre_tactics, raw_logs, model_used, alerted)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
        ON CONFLICT DO NOTHING
    """, anomaly_rows)
    print(f"    → {len(anomaly_rows)} anomalies")

    # ── Alerts ────────────────────────────────────────────────────────────────
    print("  Inserting alerts ...")
    alert_rows = []
    for i, aid in enumerate(anomaly_ids[:5]):
        alert_rows.append((
            str(uuid.uuid4()),
            now - timedelta(minutes=random.randint(1, 60)),
            aid,
            "slack",
            "https://hooks.slack.com/services/demo",
            json.dumps({"text": f"[ALERT] Anomaly detected — severity: {anomaly_templates[i][0]}"}),
            "sent",
            None,
        ))
    # Add a failed alert
    alert_rows.append((
        str(uuid.uuid4()),
        now - timedelta(minutes=10),
        anomaly_ids[0],
        "email",
        "ops@example.com",
        json.dumps({"subject": "Loggator Alert", "body": "High severity anomaly detected"}),
        "failed",
        "SMTP connection timeout",
    ))

    await conn.executemany("""
        INSERT INTO alerts (id, created_at, anomaly_id, channel, destination, payload, status, error)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
        ON CONFLICT DO NOTHING
    """, alert_rows)
    print(f"    → {len(alert_rows)} alerts")

    # ── Scheduled Analyses ────────────────────────────────────────────────────
    print("  Inserting scheduled analysis reports ...")
    report_rows = []
    for i in range(6):
        window_end = now - timedelta(hours=i * 4)
        window_start = window_end - timedelta(hours=4)
        day_index = f"logs-app-{window_end.strftime('%Y.%m.%d')}"
        services = random.sample(SERVICES, k=random.randint(2, 5))
        root_causes = random.sample([
            "Connection pool exhaustion causing cascade failures",
            "Memory leak in order processing loop — RSS growing unbounded",
            "Redis eviction policy too aggressive under load",
            "Missing index on orders.created_at causing full table scans",
            "Kafka consumer group rebalancing too frequently",
            "IAM role permissions drifted after last deployment",
        ], k=random.randint(2, 4))
        timeline_events = [
            "First ERROR detected on payment-service",
            "Circuit breaker opened for inventory-service",
            "Alert fired to Slack #incidents channel",
            "Pod restart detected on order-service",
            "Memory threshold exceeded on auth-service",
            "Error rate peaked at 340 errors/min",
        ]
        timeline = [
            f"{(window_start + timedelta(minutes=m)).strftime('%H:%M')} — {ev}"
            for m, ev in zip([5, 18, 32, 47, 65, 92], timeline_events)
        ]
        rec_pool = [
            {"priority": "immediate", "action": "Increase PostgreSQL connection pool max_connections to 50", "rationale": "Pool exhaustion is causing synchronous failures on every checkout request."},
            {"priority": "immediate", "action": "Enable Redis Sentinel for automatic failover", "rationale": "Single Redis instance is a SPOF; Sentinel provides automatic promotion on failure."},
            {"priority": "short-term", "action": "Add HPA for payment-service with CPU threshold 70%", "rationale": "Traffic spikes exceed pod capacity without horizontal autoscaling."},
            {"priority": "short-term", "action": "Configure cert-manager for automatic TLS renewal", "rationale": "Manual cert rotation has already caused near-expiry incidents."},
            {"priority": "long-term", "action": "Add composite index on (orders.user_id, orders.status)", "rationale": "Slow queries on orders table are contributing to latency SLA breaches."},
            {"priority": "long-term", "action": "Implement exponential backoff on Kafka consumer retries", "rationale": "Constant retry loops are amplifying load on downstream services."},
            {"priority": "short-term", "action": "Enforce MFA on all admin accounts in auth-service", "rationale": "Credential stuffing attempts detected — MFA would block most automated attacks."},
        ]
        recommendations = random.sample(rec_pool, k=3)
        error_count = random.randint(40, 300)
        warning_count = random.randint(20, 120)
        log_count = error_count + warning_count + random.randint(100, 500)

        report_rows.append((
            str(uuid.uuid4()),
            window_start, window_end, day_index,
            f"Analysis of {log_count} log events across {len(services)} services in the past 4 hours. "
            f"Detected {error_count} errors and {warning_count} warnings. "
            f"Primary root cause: {root_causes[0]}.",
            json.dumps(services),
            json.dumps(root_causes),
            json.dumps(timeline),
            json.dumps(recommendations),
            error_count, warning_count, log_count,
            random.randint(3, 12),
            "claude-sonnet-4-6",
            "success",
        ))

    await conn.executemany("""
        INSERT INTO scheduled_analyses (id, window_start, window_end, index_pattern,
            summary, affected_services, root_causes, timeline, recommendations,
            error_count, warning_count, log_count, chunk_count, model_used, status)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
        ON CONFLICT DO NOTHING
    """, report_rows)
    print(f"    → {len(report_rows)} analysis reports")

    await conn.close()


async def main():
    now = datetime.now(timezone.utc)
    print(f"Demo seed starting — reference time: {now.isoformat()}")
    seed_opensearch(now)
    await seed_postgres(now)
    print("\nDone! Summary:")
    print("  OpenSearch: 7 days of logs across logs-app-* indices")
    print("  Postgres:   8 summaries | 8 anomalies | 6 alerts | 6 analysis reports")
    print("\nUI endpoints:")
    print("  Web:                http://localhost:3000")
    print("  API docs:           http://localhost:8000/docs")
    print("  OpenSearch Dashboards: http://localhost:5601")


if __name__ == "__main__":
    asyncio.run(main())

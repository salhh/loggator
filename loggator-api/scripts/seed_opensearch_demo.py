#!/usr/bin/env python3
"""
Push demo log documents into OpenSearch (local Docker stack).

Runs ``seed_logs.py`` (generic app logs → logs-app-local) then
``seed_attack_logs.py`` (MITRE-flavoured lines → logs-attack-local).
Both indices match the default tenant pattern ``logs-*``.

Usage:
  docker compose -f docker-compose.local.yml run --rm seed-opensearch

Or from repo API dir with stack up:
  OPENSEARCH_HOST=localhost python scripts/seed_opensearch_demo.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    base = os.environ.copy()
    base.setdefault("OPENSEARCH_HOST", "localhost")
    base.setdefault("OPENSEARCH_PORT", "9200")

    steps = [
        ("scripts/seed_logs.py", "logs-app-local"),
        ("scripts/seed_attack_logs.py", "logs-attack-local"),
    ]
    for rel, index in steps:
        env = {**base, "LOG_SEED_INDEX": index}
        script = API_ROOT / rel
        print(f"seed_opensearch_demo: running {rel} → index {index}", flush=True)
        subprocess.run(
            [sys.executable, str(script)],
            cwd=str(API_ROOT),
            env=env,
            check=True,
        )
    print("seed_opensearch_demo: done", flush=True)


if __name__ == "__main__":
    main()

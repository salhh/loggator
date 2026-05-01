"""Threat intelligence lookups with DB-backed cache.

Supported backends (all free-tier):
  - AbuseIPDB  (env: ABUSEIPDB_API_KEY)
  - GreyNoise  (env: GREYNOISE_API_KEY)

Falls back gracefully if keys are absent — returns "unknown" reputation.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.db.models import ThreatIndicator

log = structlog.get_logger()

_ABUSEIPDB_KEY = os.getenv("ABUSEIPDB_API_KEY", "")
_GREYNOISE_KEY = os.getenv("GREYNOISE_API_KEY", "")
_CACHE_TTL_HOURS = int(os.getenv("THREAT_INTEL_CACHE_TTL_HOURS", "24"))


async def _fetch_abuseipdb(ip: str) -> Optional[dict[str, Any]]:
    if not _ABUSEIPDB_KEY:
        return None
    try:
        import aiohttp  # type: ignore
        url = "https://api.abuseipdb.com/api/v2/check"
        headers = {"Key": _ABUSEIPDB_KEY, "Accept": "application/json"}
        params = {"ipAddress": ip, "maxAgeInDays": 30}
        async with aiohttp.ClientSession() as sess:
            async with sess.get(url, headers=headers, params=params, timeout=5) as resp:
                if resp.status != 200:
                    return None
                data = (await resp.json()).get("data", {})
                score = data.get("abuseConfidenceScore", 0)
                reputation = "clean" if score < 25 else ("suspicious" if score < 75 else "malicious")
                return {
                    "source": "abuseipdb",
                    "confidence_score": score,
                    "reputation": reputation,
                    "details": {
                        "country_code": data.get("countryCode"),
                        "isp": data.get("isp"),
                        "domain": data.get("domain"),
                        "total_reports": data.get("totalReports"),
                    },
                }
    except Exception as e:
        log.warning("enrichment.abuseipdb_error", ip=ip, error=str(e))
        return None


async def _fetch_greynoise(ip: str) -> Optional[dict[str, Any]]:
    if not _GREYNOISE_KEY:
        return None
    try:
        import aiohttp  # type: ignore
        url = f"https://api.greynoise.io/v3/community/{ip}"
        headers = {"key": _GREYNOISE_KEY}
        async with aiohttp.ClientSession() as sess:
            async with sess.get(url, headers=headers, timeout=5) as resp:
                if resp.status == 404:
                    return {"source": "greynoise", "confidence_score": 0, "reputation": "clean", "details": {"noise": False}}
                if resp.status != 200:
                    return None
                data = await resp.json()
                noise = data.get("noise", False)
                riot = data.get("riot", False)  # known-good infrastructure
                reputation = "clean" if riot else ("suspicious" if noise else "unknown")
                return {
                    "source": "greynoise",
                    "confidence_score": 80 if noise else 0,
                    "reputation": reputation,
                    "details": {"noise": noise, "riot": riot, "classification": data.get("classification"), "name": data.get("name")},
                }
    except Exception as e:
        log.warning("enrichment.greynoise_error", ip=ip, error=str(e))
        return None


async def enrich_ip(session: AsyncSession, ip: str) -> dict[str, Any]:
    """Return enrichment dict for an IP, using DB cache."""
    now = datetime.now(timezone.utc)

    # Check cache
    r = await session.execute(
        select(ThreatIndicator)
        .where(ThreatIndicator.ioc_type == "ip", ThreatIndicator.value == ip)
        .limit(1)
    )
    cached = r.scalar_one_or_none()
    if cached and cached.expires_at > now:
        return {
            "ioc_type": "ip",
            "value": ip,
            "reputation": cached.reputation,
            "confidence_score": cached.confidence_score,
            "source": cached.source,
            "details": cached.details or {},
            "cached": True,
        }

    # Live lookup — try AbuseIPDB first, then GreyNoise
    result = await _fetch_abuseipdb(ip) or await _fetch_greynoise(ip)

    if result is None:
        result = {"source": "none", "confidence_score": None, "reputation": "unknown", "details": {}}

    expires_at = now + timedelta(hours=_CACHE_TTL_HOURS)

    if cached:
        cached.reputation = result["reputation"]
        cached.confidence_score = result.get("confidence_score")
        cached.source = result["source"]
        cached.details = result.get("details")
        cached.expires_at = expires_at
    else:
        row = ThreatIndicator(
            id=uuid4(),
            ioc_type="ip",
            value=ip,
            reputation=result["reputation"],
            confidence_score=result.get("confidence_score"),
            source=result["source"],
            details=result.get("details"),
            expires_at=expires_at,
        )
        session.add(row)

    try:
        await session.commit()
    except Exception:
        await session.rollback()

    return {
        "ioc_type": "ip",
        "value": ip,
        "reputation": result["reputation"],
        "confidence_score": result.get("confidence_score"),
        "source": result["source"],
        "details": result.get("details", {}),
        "cached": False,
    }


async def enrich_anomaly_iocs(
    session: AsyncSession,
    iocs: dict[str, set[str]],
    max_ips: int = 5,
) -> dict[str, Any]:
    """Enrich up to `max_ips` public IPs found in an anomaly and return summary."""
    enriched: list[dict] = []
    for ip in list(iocs.get("ip", set()))[:max_ips]:
        result = await enrich_ip(session, ip)
        enriched.append(result)
        log.info(
            "enrichment.ip_result",
            ip=ip,
            reputation=result["reputation"],
            source=result["source"],
        )
    return {
        "ips": enriched,
        "hashes": list(iocs.get("hash", set()))[:10],
        "domains": list(iocs.get("domain", set()))[:10],
    }

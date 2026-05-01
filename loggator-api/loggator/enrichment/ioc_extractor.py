"""Extract IOCs (IPs, domains, hashes) from log documents."""

from __future__ import annotations

import ipaddress
import re
from typing import Any

# IPv4 pattern — excludes private/loopback ranges
_IPV4 = re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b")
_MD5 = re.compile(r"\b([0-9a-fA-F]{32})\b")
_SHA256 = re.compile(r"\b([0-9a-fA-F]{64})\b")
_DOMAIN = re.compile(
    r"\b((?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,})\b"
)

_PRIVATE_NETS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
]

_COMMON_DOMAINS = {"localhost", "example.com", "test.local", "internal"}


def _is_public_ip(addr: str) -> bool:
    try:
        ip = ipaddress.ip_address(addr)
        return not any(ip in net for net in _PRIVATE_NETS)
    except ValueError:
        return False


def extract_iocs(docs: list[dict[str, Any]]) -> dict[str, set[str]]:
    """Return deduplicated IOC sets keyed by type."""
    ips: set[str] = set()
    hashes: set[str] = set()
    domains: set[str] = set()

    for doc in docs:
        # Check dedicated fields first
        for field in ("src_ip", "source_ip", "client_ip", "remote_addr", "ip"):
            val = doc.get(field) or (doc.get("fields") or {}).get(field, "")
            if val and _is_public_ip(str(val)):
                ips.add(str(val))

        # Scan message text
        text = doc.get("message", "")
        if isinstance(text, str):
            for m in _IPV4.finditer(text):
                if _is_public_ip(m.group(1)):
                    ips.add(m.group(1))
            for m in _SHA256.finditer(text):
                hashes.add(m.group(1).lower())
            for m in _MD5.finditer(text):
                hashes.add(m.group(1).lower())
            for m in _DOMAIN.finditer(text):
                d = m.group(1).lower()
                if d not in _COMMON_DOMAINS and "." in d:
                    domains.add(d)

    return {"ip": ips, "hash": hashes, "domain": domains}

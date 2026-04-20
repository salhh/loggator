import json
from typing import Iterator

import tiktoken
import structlog

from loggator.config import settings

log = structlog.get_logger()

# Use cl100k_base encoding (GPT-4 / most modern models) as a token approximation
_ENCODING = tiktoken.get_encoding("cl100k_base")


def _count_tokens(text: str) -> int:
    return len(_ENCODING.encode(text, disallowed_special=()))


def _doc_to_line(doc: dict) -> str:
    """Render a log document as a compact single line for the prompt."""
    ts = doc.get("@timestamp", "")
    level = doc.get("level", "")
    service = doc.get("service", "unknown")
    host = doc.get("host", "")
    message = doc.get("message", "")
    occurrences = doc.get("_occurrences", 1)

    parts = [f"[{ts}]", f"[{level}]"]
    if service:
        parts.append(f"[{service}]")
    if host:
        parts.append(f"[{host}]")
    parts.append(message)
    if occurrences > 1:
        parts.append(f"(x{occurrences})")

    return " ".join(parts)


def chunk_docs(
    docs: list[dict],
    max_tokens: int | None = None,
) -> list[str]:
    """
    Split a list of log documents into text chunks that each fit within max_tokens.
    Each chunk is a newline-joined string of log lines, ready to send to Ollama.
    Never splits a single log line across chunks.
    """
    limit = max_tokens or settings.chunk_max_tokens
    chunks: list[str] = []
    current_lines: list[str] = []
    current_tokens = 0

    for doc in docs:
        line = _doc_to_line(doc)
        line_tokens = _count_tokens(line)

        # Single line exceeds limit — truncate and include alone
        if line_tokens > limit:
            if current_lines:
                chunks.append("\n".join(current_lines))
                current_lines = []
                current_tokens = 0
            chunks.append(line[:limit * 4])  # rough char truncation
            continue

        if current_tokens + line_tokens > limit and current_lines:
            chunks.append("\n".join(current_lines))
            current_lines = []
            current_tokens = 0

        current_lines.append(line)
        current_tokens += line_tokens

    if current_lines:
        chunks.append("\n".join(current_lines))

    log.info("chunker.done", docs=len(docs), chunks=len(chunks), max_tokens=limit)
    return chunks

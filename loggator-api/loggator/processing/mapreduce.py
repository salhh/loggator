import asyncio
import json
import structlog

from loggator.ollama.client import OllamaClient
from loggator.ollama.prompts import (
    ANOMALY_PROMPT,
    SUMMARY_MAP_PROMPT,
    SUMMARY_REDUCE_PROMPT,
    ANALYSIS_MAP_PROMPT,
    ANALYSIS_REDUCE_PROMPT,
)

log = structlog.get_logger()


async def analyze_chunks_for_anomalies(
    chunks: list[str],
    client: OllamaClient,
) -> list[dict]:
    """
    Map each chunk through the anomaly prompt in parallel.
    Returns a flat list of anomaly result dicts (one per chunk that had findings).
    """
    async def _analyze_one(chunk: str, idx: int) -> dict:
        log.info("anomaly.map.chunk", idx=idx, lines=chunk.count("\n") + 1)
        result = await client.generate(ANOMALY_PROMPT, chunk)
        return result

    tasks = [_analyze_one(chunk, i) for i, chunk in enumerate(chunks)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    valid = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            log.error("anomaly.map.chunk.failed", idx=i, error=str(r))
        else:
            valid.append(r)

    return valid


async def summarize_chunks(
    chunks: list[str],
    client: OllamaClient,
) -> dict:
    """
    Map-reduce summarization:
    1. Map: send each chunk to Ollama with SUMMARY_MAP_PROMPT in parallel
    2. Reduce: merge all partial summaries into one final report
    Returns the final summary dict.
    """
    if not chunks:
        return {"summary": "No logs to summarize.", "top_issues": [], "error_count": 0, "recommendation": ""}

    # --- MAP ---
    log.info("summarize.map.start", chunks=len(chunks))

    async def _map_one(chunk: str, idx: int) -> dict:
        log.info("summarize.map.chunk", idx=idx)
        return await client.generate(SUMMARY_MAP_PROMPT, chunk)

    map_tasks = [_map_one(chunk, i) for i, chunk in enumerate(chunks)]
    map_results = await asyncio.gather(*map_tasks, return_exceptions=True)

    partial_summaries = []
    total_errors = 0
    for i, r in enumerate(map_results):
        if isinstance(r, Exception):
            log.error("summarize.map.chunk.failed", idx=i, error=str(r))
        else:
            partial_summaries.append(r)
            total_errors += int(r.get("error_count", 0))

    log.info("summarize.map.done", partial_count=len(partial_summaries))

    # --- REDUCE ---
    if len(partial_summaries) == 1:
        # Only one chunk — no reduce step needed
        return partial_summaries[0]

    reduce_input = json.dumps(partial_summaries, indent=2)
    log.info("summarize.reduce.start")
    final = await client.generate(SUMMARY_REDUCE_PROMPT, reduce_input)

    # Ensure error_count is the sum from map step (more accurate than Ollama's guess)
    final["error_count"] = total_errors
    log.info("summarize.reduce.done", error_count=total_errors)
    return final


async def analyze_chunks(chunks: list[str], client: OllamaClient) -> dict:
    """
    Deep root cause analysis via map-reduce:
    1. Map: analyse each chunk with ANALYSIS_MAP_PROMPT in parallel
    2. Reduce: merge all partial findings into one structured RCA report
    Returns the final analysis dict.
    """
    if not chunks:
        return {
            "summary": "No logs provided for analysis.",
            "affected_services": [],
            "root_causes": [],
            "timeline": [],
            "recommendations": [],
            "error_count": 0,
            "warning_count": 0,
        }

    log.info("analyze.map.start", chunks=len(chunks))

    async def _map_one(chunk: str, idx: int) -> dict:
        log.info("analyze.map.chunk", idx=idx)
        return await client.generate(ANALYSIS_MAP_PROMPT, chunk)

    map_tasks = [_map_one(chunk, i) for i, chunk in enumerate(chunks)]
    map_results = await asyncio.gather(*map_tasks, return_exceptions=True)

    partial = []
    total_errors = 0
    total_warnings = 0
    for i, r in enumerate(map_results):
        if isinstance(r, Exception):
            log.error("analyze.map.chunk.failed", idx=i, error=str(r))
        else:
            partial.append(r)
            total_errors += int(r.get("error_count", 0))
            total_warnings += int(r.get("warning_count", 0))

    log.info("analyze.map.done", partial_count=len(partial))

    if not partial:
        raise RuntimeError("All map chunks failed — Ollama may be unreachable")

    if len(partial) == 1:
        # Single chunk — synthesise the reduce shape from the map result
        m = partial[0]
        rca_list = [
            {"title": rc, "description": rc, "services": m.get("affected_services", []), "severity": "medium"}
            for rc in m.get("root_causes", [])
        ]
        return {
            "summary": m.get("summary", ""),
            "affected_services": m.get("affected_services", []),
            "root_causes": rca_list,
            "timeline": m.get("timeline_events", []),
            "recommendations": [],
            "error_count": total_errors,
            "warning_count": total_warnings,
        }

    reduce_input = json.dumps(partial, indent=2)
    log.info("analyze.reduce.start")
    final = await client.generate(ANALYSIS_REDUCE_PROMPT, reduce_input)
    final["error_count"] = total_errors
    final["warning_count"] = total_warnings
    log.info("analyze.reduce.done")
    return final

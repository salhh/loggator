import asyncio
import json
import structlog

from loggator.llm.chain import llm_chain

log = structlog.get_logger()


async def analyze_chunks_for_anomalies(
    chunks: list[str],
) -> list[dict]:
    """
    Map each chunk through the anomaly prompt in parallel.
    Returns a flat list of anomaly result dicts (one per chunk that had findings).
    """
    async def _analyze_one(chunk: str, idx: int) -> dict:
        log.info("anomaly.map.chunk", idx=idx, lines=chunk.count("\n") + 1)
        result = await llm_chain.generate("anomaly", chunk)
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
        return await llm_chain.generate("summary_map", chunk)

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
    final = await llm_chain.generate("summary_reduce", reduce_input)

    # Ensure error_count is the sum from map step (more accurate than Ollama's guess)
    final["error_count"] = total_errors
    log.info("summarize.reduce.done", error_count=total_errors)
    return final

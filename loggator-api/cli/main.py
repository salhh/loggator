import asyncio
import json
from pathlib import Path
import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(name="loggator", help="Loggator — AI-powered log analysis CLI")
console = Console()


# ── test-connection ────────────────────────────────────────────────────────────

@app.command()
def test_connection():
    """Verify connectivity to OpenSearch and Ollama."""
    asyncio.run(_test_connection())


async def _test_connection():
    from loggator.opensearch.client import get_client
    from loggator.opensearch.queries import ping, list_indices
    from loggator.config import settings
    import httpx

    console.rule("[bold]Loggator connection test[/bold]")

    # OpenSearch
    console.print(f"\n[cyan]OpenSearch[/cyan]  {settings.opensearch_host}:{settings.opensearch_port}  (auth: {settings.opensearch_auth_type})")
    client = get_client()
    ok = await ping(client)
    if ok:
        console.print("  [green][OK] Connected[/green]")
        indices = await list_indices(client)
        if indices:
            console.print(f"  Visible indices: {', '.join(indices[:10])}{'...' if len(indices) > 10 else ''}")
        else:
            console.print("  [yellow]No visible indices[/yellow]")

        # Fetch sample logs
        from loggator.opensearch.queries import search_after_logs
        docs, cursor = await search_after_logs(client, settings.opensearch_index_pattern, size=5)
        console.print(f"  Sample fetch ({settings.opensearch_index_pattern}): [green]{len(docs)} logs[/green]")
        if docs:
            console.print(f"  First log keys: {list(docs[0].keys())[:8]}")
    else:
        console.print("  [red][FAIL] Could not connect[/red]")

    await client.close()

    # Ollama
    console.print(f"\n[cyan]Ollama[/cyan]  {settings.ollama_base_url}  (model: {settings.ollama_model})")
    try:
        async with httpx.AsyncClient(timeout=5) as http:
            r = await http.get(f"{settings.ollama_base_url}/api/tags")
            if r.status_code == 200:
                models = [m["name"] for m in r.json().get("models", [])]
                console.print("  [green][OK] Reachable[/green]")
                if models:
                    console.print(f"  Available models: {', '.join(models)}")
                    if settings.ollama_model not in models:
                        console.print(f"  [yellow][WARN] Model '{settings.ollama_model}' not found — run: ollama pull {settings.ollama_model}[/yellow]")
                else:
                    console.print(f"  [yellow]No models pulled yet — run: ollama pull {settings.ollama_model}[/yellow]")
            else:
                console.print(f"  [red][FAIL] Unexpected status {r.status_code}[/red]")
    except Exception as exc:
        console.print(f"  [red][FAIL] {exc}[/red]")

    console.print()


# ── analyze-sample ─────────────────────────────────────────────────────────────

@app.command()
def analyze_sample(
    file: Path = typer.Argument(..., help="Path to a log file (one JSON object per line or plain text)"),
):
    """Feed a log file to the LLM chain and print the anomaly analysis result."""
    asyncio.run(_analyze_sample(file))


async def _analyze_sample(file: Path):
    from loggator.processing.preprocessor import preprocess
    from loggator.processing.chunker import chunk_docs
    from loggator.processing.mapreduce import analyze_chunks_for_anomalies
    from loggator.config import settings

    if not file.exists():
        console.print(f"[red]File not found: {file}[/red]")
        raise typer.Exit(1)

    raw = file.read_text(encoding="utf-8")
    lines = [l.strip() for l in raw.splitlines() if l.strip()]

    # Parse: try JSON per line, fall back to plain-text dicts
    docs = []
    for line in lines:
        try:
            docs.append(json.loads(line))
        except json.JSONDecodeError:
            docs.append({"message": line, "level": "INFO", "@timestamp": ""})

    console.print(f"[cyan]Loaded {len(docs)} log entries[/cyan]")

    # Preprocess
    clean = preprocess(docs)
    console.print(f"[cyan]After preprocessing: {len(clean)} entries (dropped {len(docs) - len(clean)} noise/debug)[/cyan]")

    # Chunk
    chunks = chunk_docs(clean)
    console.print(f"[cyan]Split into {len(chunks)} chunk(s) for analysis (provider: {settings.llm_provider})[/cyan]\n")

    # Analyze
    results = await analyze_chunks_for_anomalies(chunks)

    for i, result in enumerate(results):
        if len(results) > 1:
            console.print(f"\n[bold]--- Chunk {i + 1} / {len(results)} ---[/bold]")
        console.print_json(json.dumps(result, indent=2, default=str))


# ── report ─────────────────────────────────────────────────────────────────────

@app.command()
def report():
    """Print the latest batch summary."""
    asyncio.run(_report())


async def _report():
    from loggator.db.session import AsyncSessionLocal
    from loggator.db.repository import SummaryRepository
    from loggator.tenancy.bootstrap import get_default_tenant_id

    async with AsyncSessionLocal() as session:
        tenant_id = await get_default_tenant_id(session)
        repo = SummaryRepository(session, tenant_id)
        summary = await repo.get_latest()

    if not summary:
        console.print("[yellow]No summaries yet. Wait for the batch scheduler or run 'loggator batch-trigger'.[/yellow]")
        return

    console.rule(f"[bold]Summary[/bold] — {summary.window_start.isoformat()} → {summary.window_end.isoformat()}")
    console.print(f"\n[bold]Index:[/bold] {summary.index_pattern}")
    console.print(f"[bold]Model:[/bold] {summary.model_used}")
    console.print(f"[bold]Errors:[/bold] {summary.error_count}")
    console.print(f"\n[bold]Summary:[/bold]\n{summary.summary}")
    if summary.top_issues:
        console.print("\n[bold]Top issues:[/bold]")
        for issue in summary.top_issues:
            console.print(f"  • {issue}")
    if summary.recommendation:
        console.print(f"\n[bold]Recommendation:[/bold] {summary.recommendation}")


# ── watch ──────────────────────────────────────────────────────────────────────

@app.command()
def watch():
    """Live tail of anomalies from the database."""
    asyncio.run(_watch())


async def _watch():
    from loggator.db.session import AsyncSessionLocal
    from loggator.db.repository import AnomalyRepository
    from loggator.tenancy.bootstrap import get_default_tenant_id
    import time

    console.print("[cyan]Watching for anomalies... (Ctrl+C to stop)[/cyan]\n")
    seen: set = set()

    try:
        while True:
            async with AsyncSessionLocal() as session:
                tenant_id = await get_default_tenant_id(session)
                repo = AnomalyRepository(session, tenant_id)
                anomalies = await repo.list(limit=20)

            for a in reversed(anomalies):
                if a.id not in seen:
                    seen.add(a.id)
                    colour = {"high": "red", "medium": "yellow", "low": "green"}.get(a.severity, "white")
                    console.print(
                        f"[{colour}][{a.severity.upper()}][/{colour}] "
                        f"{a.detected_at.isoformat()}  {a.summary[:120]}"
                    )

            await asyncio.sleep(5)
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped.[/dim]")


# ── alerts ─────────────────────────────────────────────────────────────────────

@app.command()
def alerts():
    """List recent alert dispatch history."""
    asyncio.run(_alerts())


async def _alerts():
    from loggator.db.session import AsyncSessionLocal
    from loggator.db.repository import AlertRepository
    from loggator.tenancy.bootstrap import get_default_tenant_id

    async with AsyncSessionLocal() as session:
        tenant_id = await get_default_tenant_id(session)
        repo = AlertRepository(session, tenant_id)
        rows = await repo.list(limit=20)

    if not rows:
        console.print("[yellow]No alerts dispatched yet.[/yellow]")
        return

    table = Table(title="Recent Alerts")
    table.add_column("Time", style="dim")
    table.add_column("Channel")
    table.add_column("Status")
    table.add_column("Destination")
    table.add_column("Error")

    for a in rows:
        status_colour = {"sent": "green", "failed": "red", "pending": "yellow"}.get(a.status, "white")
        table.add_row(
            a.created_at.isoformat()[:19],
            a.channel,
            f"[{status_colour}]{a.status}[/{status_colour}]",
            a.destination[:40],
            a.error or "",
        )

    console.print(table)


# ── batch-trigger ──────────────────────────────────────────────────────────────

@app.command()
def batch_trigger():
    """Manually trigger a batch summary run."""
    asyncio.run(_batch_trigger())


async def _batch_trigger():
    from loggator.pipelines.batch import run_batch
    console.print("[cyan]Running batch summarizer...[/cyan]")
    await run_batch()
    console.print("[green]Done.[/green]")


if __name__ == "__main__":
    app()

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from dbctx import __version__
from dbctx.config import AppConfig, load_config, snapshot_path
from dbctx.models import ExplainResult
from dbctx.mysql import build_snapshot, explain as mysql_explain
from dbctx.render import (
    emit_json,
    render_indexes,
    render_review,
    render_schema,
    render_stats,
    render_tables,
)
from dbctx.review import review_sql
from dbctx.snapshot import read_snapshot, resolve_table, write_snapshot

app = typer.Typer(no_args_is_help=True, help="AI-friendly database context CLI.")
console = Console()

Format = Annotated[str, typer.Option("--format", help="Output format: text or json")]
ConfigOpt = Annotated[str | None, typer.Option("--config", help="Path to dbctx.yml")]


def _load(config: str | None) -> tuple[AppConfig, Path]:
    try:
        return load_config(config)
    except Exception as exc:
        raise typer.BadParameter(str(exc)) from exc


def _snapshot(config: str | None):
    cfg, cfg_path = _load(config)
    return cfg, cfg_path, read_snapshot(snapshot_path(cfg, cfg_path))


def _connection(cfg: AppConfig, name: str, purpose: str):
    if name not in cfg.connections:
        raise typer.BadParameter(f"Connection not found: {name}")
    conn = cfg.connections[name]
    if purpose not in conn.allow:
        raise typer.BadParameter(f"Connection `{name}` does not allow `{purpose}`")
    dsn = conn.dsn()
    if not dsn:
        raise typer.BadParameter(f"Environment variable `{conn.dsn_env}` is not set")
    return conn, dsn


def _check_format(fmt: str) -> str:
    if fmt not in {"text", "json"}:
        raise typer.BadParameter("--format must be text or json")
    return fmt


@app.command()
def version() -> None:
    """Print dbctx version."""
    console.print(__version__)


@app.command()
def init(
    force: Annotated[bool, typer.Option("--force", help="Overwrite existing files")] = False,
) -> None:
    """Create dbctx.yml, .dbctx/, docs, and skill templates."""
    root = Path.cwd()
    template_dir = Path(__file__).parent / "templates"
    targets = {
        "dbctx.yml": root / "dbctx.yml",
        "dbctx-agent-usage.md": root / "docs" / "dbctx-agent-usage.md",
        "SKILL.md": root / "skills" / "dbctx" / "SKILL.md",
    }
    for source_name, target in targets.items():
        if target.exists() and not force:
            console.print(f"[yellow]skip existing[/yellow] {target}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(template_dir / source_name, target)
        console.print(f"[green]created[/green] {target}")
    (root / ".dbctx").mkdir(exist_ok=True)
    gitignore = root / ".dbctx" / ".gitignore"
    if not gitignore.exists() or force:
        gitignore.write_text("# Keep local transient files out of git.\n*.tmp\n", encoding="utf-8")
        console.print(f"[green]created[/green] {gitignore}")


@app.command()
def guide() -> None:
    """Print the short workflow for AI coding agents."""
    console.print(
        """[bold]dbctx workflow[/bold]
1. Identify affected database tables.
2. Inspect context:
   dbctx schema <table>
   dbctx indexes <table>
   dbctx stats <table>
3. Review every concrete SQL:
   dbctx review --sql "<sql>"
4. If a test verification DB is configured:
   dbctx explain --conn test_verify --sql "<sql>"
5. Fix error/high-risk findings before finalizing.

Snapshot context should come from production-like metadata.
Explain should run on a test/verification database and is not a production performance guarantee.
"""
    )


@app.command()
def snapshot(
    conn: Annotated[str, typer.Option("--conn", help="Connection name for metadata snapshot")] = "prod_snapshot",
    config: ConfigOpt = None,
    format: Format = "text",
) -> None:
    """Generate .dbctx/snapshot.json from a production-like read-only MySQL connection."""
    fmt = _check_format(format)
    cfg, cfg_path = _load(config)
    _, dsn = _connection(cfg, conn, "snapshot")
    snap = build_snapshot(conn, dsn, cfg.mysql.default_schema or None)
    out = snapshot_path(cfg, cfg_path)
    write_snapshot(snap, out)
    result = {"snapshot": str(out), "tables": len(snap.tables), "source": snap.source.model_dump()}
    if fmt == "json":
        emit_json(result)
    else:
        console.print(f"[green]snapshot written[/green] {out}")
        console.print(f"tables: {len(snap.tables)}")


@app.command()
def tables(
    search: Annotated[str | None, typer.Option("--search", help="Filter by table name or comment")] = None,
    config: ConfigOpt = None,
    format: Format = "text",
) -> None:
    """List tables from the local snapshot."""
    fmt = _check_format(format)
    _, _, snap = _snapshot(config)
    if fmt == "json":
        values = [
            t.model_dump(mode="json")
            for t in snap.tables.values()
            if not search or search.lower() in f"{t.schema_name}.{t.name} {t.comment}".lower()
        ]
        emit_json(values)
    else:
        render_tables(snap, search)


@app.command()
def schema(table: str, config: ConfigOpt = None, format: Format = "text") -> None:
    """Show columns for a table from the local snapshot."""
    fmt = _check_format(format)
    cfg, _, snap = _snapshot(config)
    info = resolve_table(snap, table, cfg.mysql.default_schema)
    emit_json(info) if fmt == "json" else render_schema(info)


@app.command()
def indexes(table: str, config: ConfigOpt = None, format: Format = "text") -> None:
    """Show indexes for a table from the local snapshot."""
    fmt = _check_format(format)
    cfg, _, snap = _snapshot(config)
    info = resolve_table(snap, table, cfg.mysql.default_schema)
    if fmt == "json":
        emit_json([idx.model_dump(mode="json") for idx in info.indexes])
    else:
        render_indexes(info)


@app.command()
def stats(table: str, config: ConfigOpt = None, format: Format = "text") -> None:
    """Show table statistics from the local snapshot."""
    fmt = _check_format(format)
    cfg, _, snap = _snapshot(config)
    info = resolve_table(snap, table, cfg.mysql.default_schema)
    if fmt == "json":
        emit_json(
            {
                "schema": info.schema_name,
                "table": info.name,
                "row_count": info.row_count,
                "large_table": (info.row_count or 0) >= cfg.rules.large_table_threshold,
                "data_size_bytes": info.data_size_bytes,
                "index_size_bytes": info.index_size_bytes,
                "engine": info.engine,
                "partitions": [p.model_dump(mode="json") for p in info.partitions],
            }
        )
    else:
        render_stats(info, cfg.rules.large_table_threshold)


@app.command()
def review(
    sql: Annotated[str | None, typer.Option("--sql", help="Concrete SQL to review")] = None,
    file: Annotated[Path | None, typer.Option("--file", help="File containing SQL")] = None,
    config: ConfigOpt = None,
    format: Format = "text",
) -> None:
    """Review SQL offline using the local snapshot."""
    fmt = _check_format(format)
    cfg, _, snap = _snapshot(config)
    statement = _read_sql(sql, file)
    result = review_sql(statement, snap, cfg.rules, cfg.mysql.default_schema)
    if fmt == "json":
        emit_json(result)
    else:
        render_review(result)
    if result.risk == "high":
        raise typer.Exit(2)


@app.command()
def explain(
    sql: Annotated[str | None, typer.Option("--sql", help="Concrete SELECT SQL to explain")] = None,
    file: Annotated[Path | None, typer.Option("--file", help="File containing SELECT SQL")] = None,
    conn: Annotated[str, typer.Option("--conn", help="Verification connection name")] = "test_verify",
    config: ConfigOpt = None,
    format: Format = "text",
) -> None:
    """Run EXPLAIN against a read-only test/verification MySQL connection."""
    fmt = _check_format(format)
    statement = _read_sql(sql, file).strip().rstrip(";")
    lowered = statement.lower()
    if not (lowered.startswith("select") or lowered.startswith("explain")):
        raise typer.BadParameter("explain only accepts SELECT or EXPLAIN statements")
    cfg, _ = _load(config)
    _, dsn = _connection(cfg, conn, "explain")
    if lowered.startswith("explain"):
        statement = statement.split(None, 1)[1]
    raw = mysql_explain(conn, dsn, statement)
    warning = (
        "Explain ran on verification DB. Use snapshot stats/indexes for production risk judgment."
    )
    result = ExplainResult(connection=conn, warning=warning, raw=raw)
    if fmt == "json":
        emit_json(result)
    else:
        console.print(f"[bold]Connection:[/bold] {conn}")
        console.print(f"[yellow]{warning}[/yellow]")
        console.print(json.dumps(raw, ensure_ascii=False, indent=2, default=str))


@app.command()
def doctor(config: ConfigOpt = None, format: Format = "text") -> None:
    """Check configuration, snapshot, and configured connection environment variables."""
    fmt = _check_format(format)
    checks = []
    try:
        cfg, cfg_path = _load(config)
        checks.append({"name": "config", "ok": True, "detail": str(cfg_path)})
        snap_path = snapshot_path(cfg, cfg_path)
        checks.append({"name": "snapshot", "ok": snap_path.exists(), "detail": str(snap_path)})
        for name, conn in cfg.connections.items():
            checks.append(
                {
                    "name": f"connection:{name}",
                    "ok": conn.dsn() is not None,
                    "detail": f"{conn.dsn_env} {'is set' if conn.dsn() else 'is not set'}; allow={conn.allow}",
                }
            )
    except Exception as exc:
        checks.append({"name": "config", "ok": False, "detail": str(exc)})
    if fmt == "json":
        emit_json(checks)
    else:
        for check in checks:
            status = "[green]ok[/green]" if check["ok"] else "[red]fail[/red]"
            console.print(f"{status} {check['name']}: {check['detail']}")
    if any(not c["ok"] for c in checks):
        raise typer.Exit(1)


def _read_sql(sql: str | None, file: Path | None) -> str:
    if sql and file:
        raise typer.BadParameter("Use either --sql or --file, not both")
    if sql:
        return sql
    if file:
        suffix = file.suffix.lower()
        if suffix not in {".sql", ".txt"}:
            raise typer.BadParameter(
                "v1 only reads .sql/.txt files. For XML/Java/Kotlin dynamic SQL, construct a concrete SQL and pass --sql."
            )
        return file.read_text(encoding="utf-8")
    raise typer.BadParameter("Provide --sql or --file")


if __name__ == "__main__":
    app()


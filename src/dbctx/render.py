from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.table import Table

from dbctx.models import DatabaseSnapshot, ReviewResult, TableInfo

console = Console()


def emit_json(value: Any) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    console.print(json.dumps(value, ensure_ascii=False, indent=2))


def render_tables(snapshot: DatabaseSnapshot, search: str | None = None) -> None:
    table = Table(title="Tables")
    table.add_column("Table")
    table.add_column("Rows", justify="right")
    table.add_column("Comment")
    query = (search or "").lower()
    for item in sorted(snapshot.tables.values(), key=lambda t: (t.schema_name, t.name)):
        full_name = f"{item.schema_name}.{item.name}"
        if query and query not in full_name.lower() and query not in item.comment.lower():
            continue
        table.add_row(full_name, str(item.row_count or ""), item.comment)
    console.print(table)


def render_schema(table_info: TableInfo) -> None:
    table = Table(title=f"Schema: {table_info.schema_name}.{table_info.name}")
    table.add_column("Column")
    table.add_column("Type")
    table.add_column("Nullable")
    table.add_column("Default")
    table.add_column("Comment")
    for col in sorted(table_info.columns, key=lambda c: c.ordinal):
        table.add_row(col.name, col.type, "YES" if col.nullable else "NO", col.default or "", col.comment)
    console.print(table)


def render_indexes(table_info: TableInfo) -> None:
    table = Table(title=f"Indexes: {table_info.schema_name}.{table_info.name}")
    table.add_column("Index")
    table.add_column("Unique")
    table.add_column("Columns")
    table.add_column("Cardinality")
    for index in table_info.indexes:
        cardinalities = ["" if c.cardinality is None else str(c.cardinality) for c in index.columns]
        table.add_row(
            index.name,
            "YES" if index.unique else "NO",
            ", ".join(index.column_names),
            ", ".join(cardinalities),
        )
    console.print(table)


def render_stats(table_info: TableInfo, large_threshold: int) -> None:
    table = Table(title=f"Stats: {table_info.schema_name}.{table_info.name}")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("rows_estimate", str(table_info.row_count or ""))
    table.add_row("large_table", "YES" if (table_info.row_count or 0) >= large_threshold else "NO")
    table.add_row("data_size_bytes", str(table_info.data_size_bytes or ""))
    table.add_row("index_size_bytes", str(table_info.index_size_bytes or ""))
    table.add_row("engine", table_info.engine or "")
    table.add_row("partitions", str(len(table_info.partitions)))
    console.print(table)


def render_review(result: ReviewResult) -> None:
    console.print(f"[bold]Risk:[/bold] {result.risk}")
    if result.tables:
        console.print(f"[bold]Tables:[/bold] {', '.join(result.tables)}")
    if result.matched_indexes:
        console.print(f"[bold]Matched indexes:[/bold] {', '.join(result.matched_indexes)}")
    if not result.findings:
        console.print("[green]No findings.[/green]")
        return
    table = Table(title="Findings")
    table.add_column("Severity")
    table.add_column("Code")
    table.add_column("Message")
    table.add_column("Suggestion")
    for finding in result.findings:
        table.add_row(finding.severity, finding.code, finding.message, finding.suggestion or "")
    console.print(table)


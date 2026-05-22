from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import ValidationError

from dbctx.models import DatabaseSnapshot, TableInfo


def write_snapshot(snapshot: DatabaseSnapshot, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(tmp, path)


def read_snapshot(path: Path) -> DatabaseSnapshot:
    if not path.exists():
        raise FileNotFoundError(f"Snapshot not found: {path}. Run `dbctx snapshot` first.")
    try:
        return DatabaseSnapshot.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as exc:
        raise ValueError(f"Invalid snapshot file: {path}: {exc}") from exc


def resolve_table(snapshot: DatabaseSnapshot, name: str, default_schema: str = "") -> TableInfo:
    lowered = name.lower()
    if "." in lowered:
        schema, table = lowered.split(".", 1)
        key = f"{schema}.{table}"
        if key in snapshot.tables:
            return snapshot.tables[key]
        raise KeyError(f"Table not found in snapshot: {name}")

    matches = [
        table
        for table in snapshot.tables.values()
        if table.name.lower() == lowered
        and (not default_schema or table.schema_name.lower() == default_schema.lower())
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches and default_schema:
        matches = [table for table in snapshot.tables.values() if table.name.lower() == lowered]
        if len(matches) == 1:
            return matches[0]
    if len(matches) > 1:
        candidates = ", ".join(f"{t.schema_name}.{t.name}" for t in matches)
        raise KeyError(f"Ambiguous table name `{name}`. Use schema.table. Candidates: {candidates}")
    raise KeyError(f"Table not found in snapshot: {name}")


from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class ColumnInfo(BaseModel):
    name: str
    type: str
    nullable: bool
    default: str | None = None
    comment: str = ""
    ordinal: int


class IndexColumn(BaseModel):
    name: str
    seq: int
    cardinality: int | None = None


class IndexInfo(BaseModel):
    name: str
    unique: bool
    columns: list[IndexColumn]

    @property
    def column_names(self) -> list[str]:
        return [col.name for col in sorted(self.columns, key=lambda c: c.seq)]


class PartitionInfo(BaseModel):
    name: str
    row_count: int | None = None


class TableInfo(BaseModel):
    schema_name: str
    name: str
    comment: str = ""
    engine: str | None = None
    row_count: int | None = None
    data_size_bytes: int | None = None
    index_size_bytes: int | None = None
    columns: list[ColumnInfo] = Field(default_factory=list)
    indexes: list[IndexInfo] = Field(default_factory=list)
    partitions: list[PartitionInfo] = Field(default_factory=list)

    def column_map(self) -> dict[str, ColumnInfo]:
        return {col.name.lower(): col for col in self.columns}

    def index_columns(self) -> list[list[str]]:
        return [idx.column_names for idx in self.indexes]


class SnapshotSource(BaseModel):
    connection: str
    schema_name: str
    server_version: str | None = None


class DatabaseSnapshot(BaseModel):
    version: int = 1
    engine: Literal["mysql"] = "mysql"
    captured_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    source: SnapshotSource
    tables: dict[str, TableInfo]


class Finding(BaseModel):
    severity: Literal["error", "warning", "info"]
    code: str
    message: str
    suggestion: str | None = None


class ReviewTableContext(BaseModel):
    table: str
    row_count: int | None = None
    data_size_bytes: int | None = None
    index_size_bytes: int | None = None
    predicate_columns: list[str] = Field(default_factory=list)
    order_columns: list[str] = Field(default_factory=list)
    join_columns: list[str] = Field(default_factory=list)
    indexes: list[dict[str, object]] = Field(default_factory=list)


class ReviewResult(BaseModel):
    risk: Literal["low", "medium", "high"]
    tables: list[str] = Field(default_factory=list)
    matched_indexes: list[str] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    context: list[ReviewTableContext] = Field(default_factory=list)
    analysis_guidance: list[str] = Field(default_factory=list)


class ExplainResult(BaseModel):
    connection: str
    warning: str | None = None
    raw: object

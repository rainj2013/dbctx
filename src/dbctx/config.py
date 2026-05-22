from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class SnapshotConfig(BaseModel):
    path: str = ".dbctx/snapshot.json"


class ConnectionConfig(BaseModel):
    type: Literal["mysql"] = "mysql"
    dsn_env: str
    readonly: bool = True
    allow: list[Literal["snapshot", "explain"]] = Field(default_factory=list)

    def dsn(self) -> str | None:
        return os.environ.get(self.dsn_env)


class MySQLConfig(BaseModel):
    default_schema: str = ""


class PrivacyConfig(BaseModel):
    sample_rows: bool = False
    mask_columns: list[str] = Field(default_factory=list)


class RulesConfig(BaseModel):
    large_table_threshold: int = 1_000_000
    forbid_select_star: bool = True
    forbid_deep_offset: bool = True
    deep_offset_threshold: int = 10_000
    require_where_for_update_delete: bool = True
    soft_delete_columns: list[str] = Field(default_factory=lambda: ["deleted", "is_deleted"])
    tenant_columns: list[str] = Field(default_factory=lambda: ["tenant_id"])


class AppConfig(BaseModel):
    version: int = 1
    snapshot: SnapshotConfig = Field(default_factory=SnapshotConfig)
    connections: dict[str, ConnectionConfig] = Field(default_factory=dict)
    mysql: MySQLConfig = Field(default_factory=MySQLConfig)
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)
    rules: RulesConfig = Field(default_factory=RulesConfig)


def find_config_path(start: Path | None = None) -> Path | None:
    current = (start or Path.cwd()).resolve()
    for directory in [current, *current.parents]:
        candidate = directory / "dbctx.yml"
        if candidate.exists():
            return candidate
    return None


def load_config(path: str | None = None) -> tuple[AppConfig, Path]:
    config_path = Path(path).resolve() if path else find_config_path()
    if not config_path:
        raise FileNotFoundError("dbctx.yml not found. Run `dbctx init` first.")
    with config_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return AppConfig.model_validate(data), config_path


def snapshot_path(config: AppConfig, config_path: Path) -> Path:
    path = Path(config.snapshot.path)
    if not path.is_absolute():
        path = config_path.parent / path
    return path


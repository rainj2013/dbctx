from __future__ import annotations

from collections import defaultdict
from urllib.parse import unquote, urlparse
import re
from typing import Any

import pymysql
from pymysql.connections import Connection

from dbctx.models import (
    ColumnInfo,
    DatabaseSnapshot,
    IndexColumn,
    IndexInfo,
    PartitionInfo,
    SnapshotSource,
    TableInfo,
)


def connect(dsn: str) -> Connection:
    params = parse_mysql_dsn(dsn)
    return pymysql.connect(
        **params,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        read_timeout=30,
        write_timeout=30,
    )


def parse_mysql_dsn(dsn: str) -> dict[str, Any]:
    if dsn.startswith("mysql://"):
        parsed = urlparse(dsn)
        return {
            "host": parsed.hostname or "127.0.0.1",
            "port": parsed.port or 3306,
            "user": unquote(parsed.username or ""),
            "password": unquote(parsed.password or ""),
            "database": parsed.path.lstrip("/") or None,
            "charset": "utf8mb4",
        }

    match = re.match(
        r"^(?P<user>[^:@/]+)(:(?P<password>[^@/]*))?@tcp\((?P<host>[^:)]+)(:(?P<port>\d+))?\)/(?P<db>[^?]+)",
        dsn,
    )
    if match:
        return {
            "host": match.group("host"),
            "port": int(match.group("port") or 3306),
            "user": match.group("user"),
            "password": match.group("password") or "",
            "database": match.group("db"),
            "charset": "utf8mb4",
        }

    raise ValueError(
        "Unsupported MySQL DSN. Use mysql://user:pass@host:3306/db "
        "or user:pass@tcp(host:3306)/db"
    )


def _query(conn: Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def _current_schema(conn: Connection) -> str:
    row = _query(conn, "select database() as schema_name")[0]
    if not row["schema_name"]:
        raise ValueError("No database selected in DSN. Include /schema_name in the MySQL DSN.")
    return str(row["schema_name"])


def server_version(conn: Connection) -> str:
    row = _query(conn, "select version() as version")[0]
    return str(row["version"])


def build_snapshot(conn_name: str, dsn: str, schema_name: str | None = None) -> DatabaseSnapshot:
    conn = connect(dsn)
    try:
        schema = schema_name or _current_schema(conn)
        tables = _tables(conn, schema)
        _attach_columns(conn, schema, tables)
        _attach_indexes(conn, schema, tables)
        _attach_partitions(conn, schema, tables)
        return DatabaseSnapshot(
            source=SnapshotSource(
                connection=conn_name,
                schema_name=schema,
                server_version=server_version(conn),
            ),
            tables=tables,
        )
    finally:
        conn.close()


def _tables(conn: Connection, schema: str) -> dict[str, TableInfo]:
    rows = _query(
        conn,
        """
        select table_schema as table_schema, table_name as table_name,
               table_comment as table_comment, table_rows as table_rows,
               data_length as data_length, index_length as index_length,
               engine as engine
        from information_schema.tables
        where table_schema = %s and table_type = 'BASE TABLE'
        order by table_name
        """,
        (schema,),
    )
    result: dict[str, TableInfo] = {}
    for row in rows:
        key = f"{row['table_schema']}.{row['table_name']}".lower()
        result[key] = TableInfo(
            schema_name=row["table_schema"],
            name=row["table_name"],
            comment=row.get("table_comment") or "",
            engine=row.get("engine"),
            row_count=row.get("table_rows"),
            data_size_bytes=row.get("data_length"),
            index_size_bytes=row.get("index_length"),
        )
    return result


def _attach_columns(conn: Connection, schema: str, tables: dict[str, TableInfo]) -> None:
    rows = _query(
        conn,
        """
        select table_schema as table_schema, table_name as table_name,
               column_name as column_name, column_type as column_type,
               is_nullable as is_nullable, column_default as column_default,
               column_comment as column_comment, ordinal_position as ordinal_position
        from information_schema.columns
        where table_schema = %s
        order by table_name, ordinal_position
        """,
        (schema,),
    )
    for row in rows:
        key = f"{row['table_schema']}.{row['table_name']}".lower()
        if key not in tables:
            continue
        tables[key].columns.append(
            ColumnInfo(
                name=row["column_name"],
                type=row["column_type"],
                nullable=str(row["is_nullable"]).upper() == "YES",
                default=None if row["column_default"] is None else str(row["column_default"]),
                comment=row.get("column_comment") or "",
                ordinal=int(row["ordinal_position"]),
            )
        )


def _attach_indexes(conn: Connection, schema: str, tables: dict[str, TableInfo]) -> None:
    rows = _query(
        conn,
        """
        select table_schema as table_schema, table_name as table_name,
               index_name as index_name, non_unique as non_unique,
               seq_in_index as seq_in_index, column_name as column_name,
               cardinality as cardinality
        from information_schema.statistics
        where table_schema = %s
        order by table_name, index_name, seq_in_index
        """,
        (schema,),
    )
    grouped: dict[str, dict[str, list[IndexColumn]]] = defaultdict(lambda: defaultdict(list))
    unique_flags: dict[tuple[str, str], bool] = {}
    for row in rows:
        table_key = f"{row['table_schema']}.{row['table_name']}".lower()
        if table_key not in tables:
            continue
        idx_name = row["index_name"]
        grouped[table_key][idx_name].append(
            IndexColumn(
                name=row["column_name"],
                seq=int(row["seq_in_index"]),
                cardinality=row.get("cardinality"),
            )
        )
        unique_flags[(table_key, idx_name)] = int(row["non_unique"]) == 0

    for table_key, indexes in grouped.items():
        for index_name, columns in indexes.items():
            tables[table_key].indexes.append(
                IndexInfo(
                    name=index_name,
                    unique=unique_flags[(table_key, index_name)],
                    columns=sorted(columns, key=lambda c: c.seq),
                )
            )


def _attach_partitions(conn: Connection, schema: str, tables: dict[str, TableInfo]) -> None:
    rows = _query(
        conn,
        """
        select table_schema as table_schema, table_name as table_name,
               partition_name as partition_name, table_rows as table_rows
        from information_schema.partitions
        where table_schema = %s and partition_name is not null
        order by table_name, partition_ordinal_position
        """,
        (schema,),
    )
    for row in rows:
        key = f"{row['table_schema']}.{row['table_name']}".lower()
        if key not in tables:
            continue
        tables[key].partitions.append(
            PartitionInfo(name=row["partition_name"], row_count=row.get("table_rows"))
        )


def explain(conn_name: str, dsn: str, sql: str) -> dict[str, Any]:
    conn = connect(dsn)
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(f"EXPLAIN FORMAT=JSON {sql}")
            except Exception:
                cur.execute(f"EXPLAIN {sql}")
            rows = cur.fetchall()
        return {"connection": conn_name, "rows": rows}
    finally:
        conn.close()

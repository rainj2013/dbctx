from __future__ import annotations

import re
from dataclasses import dataclass

import sqlglot
from sqlglot import exp

from dbctx.config import RulesConfig
from dbctx.models import DatabaseSnapshot, Finding, ReviewResult, TableInfo
from dbctx.review.result import build_result
from dbctx.snapshot import resolve_table


@dataclass
class SQLContext:
    statement: exp.Expression
    raw_sql: str
    tables: list[TableInfo]
    predicates: set[str]
    order_columns: list[str]
    join_columns: set[str]
    limit_offset: int | None
    selected_star: bool
    matched_indexes: list[str]


def review_sql(sql: str, snapshot: DatabaseSnapshot, rules: RulesConfig, default_schema: str = "") -> ReviewResult:
    findings: list[Finding] = []
    try:
        statement = sqlglot.parse_one(sql, read="mysql")
    except Exception as exc:
        return build_result(
            [],
            [],
            [
                Finding(
                    severity="warning",
                    code="sql_parse_failed",
                    message=f"SQL parser could not parse this statement: {exc}",
                    suggestion="Review the concrete SQL variant manually or simplify dynamic SQL before review.",
                )
            ],
        )

    table_names = _table_names(statement)
    tables: list[TableInfo] = []
    for name in table_names:
        try:
            tables.append(resolve_table(snapshot, name, default_schema))
        except KeyError as exc:
            findings.append(
                Finding(
                    severity="warning",
                    code="table_not_in_snapshot",
                    message=str(exc),
                    suggestion="Refresh the snapshot or use schema.table if the table name is ambiguous.",
                )
            )

    ctx = SQLContext(
        statement=statement,
        raw_sql=sql,
        tables=tables,
        predicates=_predicate_columns(statement),
        order_columns=_order_columns(statement),
        join_columns=_join_columns(statement),
        limit_offset=_limit_offset(statement, sql),
        selected_star=any(isinstance(node, exp.Star) for node in statement.find_all(exp.Star)),
        matched_indexes=[],
    )

    if rules.forbid_select_star and ctx.selected_star:
        findings.append(
            Finding(
                severity="warning",
                code="select_star",
                message="Query uses SELECT *.",
                suggestion="Select only required columns to reduce IO and avoid fragile column coupling.",
            )
        )

    if isinstance(statement, (exp.Update, exp.Delete)) and rules.require_where_for_update_delete:
        if statement.args.get("where") is None:
            findings.append(
                Finding(
                    severity="error",
                    code="write_without_where",
                    message="UPDATE/DELETE statement has no WHERE clause.",
                    suggestion="Add a selective WHERE clause or document why this full-table write is intended.",
                )
            )

    for table in tables:
        _review_table_context(table, ctx, rules, findings)

    if rules.forbid_deep_offset and ctx.limit_offset is not None and ctx.limit_offset >= rules.deep_offset_threshold:
        findings.append(
            Finding(
                severity="warning",
                code="deep_offset_pagination",
                message=f"Query uses deep offset pagination: offset={ctx.limit_offset}.",
                suggestion="Prefer cursor pagination using an indexed monotonic column such as id or created_at.",
            )
        )

    _review_like_prefix(sql, findings)
    _review_index_functions(statement, tables, findings)

    return build_result([f"{t.schema_name}.{t.name}" for t in tables], ctx.matched_indexes, findings)


def _review_table_context(table: TableInfo, ctx: SQLContext, rules: RulesConfig, findings: list[Finding]) -> None:
    columns = table.column_map()
    table_predicates = {col for col in ctx.predicates if col in columns}
    matched = _matched_indexes(table, table_predicates, ctx.order_columns)
    ctx.matched_indexes.extend(matched)

    is_large = (table.row_count or 0) >= rules.large_table_threshold
    if is_large and not table_predicates:
        findings.append(
            Finding(
                severity="error",
                code="large_table_without_predicate",
                message=f"{table.schema_name}.{table.name} is a large table but query has no recognized predicate on it.",
                suggestion="Add selective predicates that match an index prefix.",
            )
        )
    elif is_large and not matched:
        findings.append(
            Finding(
                severity="warning",
                code="large_table_without_matching_index",
                message=f"{table.schema_name}.{table.name} is a large table and predicates do not match any index prefix.",
                suggestion="Use columns from an existing index prefix or add an index in a migration.",
            )
        )

    for soft_col in rules.soft_delete_columns:
        if soft_col.lower() in columns and soft_col.lower() not in table_predicates:
            findings.append(
                Finding(
                    severity="warning",
                    code="missing_soft_delete_filter",
                    message=f"{table.schema_name}.{table.name} has `{soft_col}` but query does not filter it.",
                    suggestion=f"Add `{soft_col} = 0` when querying active rows.",
                )
            )
            break

    for tenant_col in rules.tenant_columns:
        if tenant_col.lower() in columns and tenant_col.lower() not in table_predicates:
            findings.append(
                Finding(
                    severity="warning",
                    code="missing_tenant_filter",
                    message=f"{table.schema_name}.{table.name} has `{tenant_col}` but query does not filter it.",
                    suggestion=f"Add `{tenant_col}` filter for tenant-scoped queries.",
                )
            )
            break

    for join_col in ctx.join_columns:
        if join_col in columns and not _has_index_starting_with(table, join_col):
            findings.append(
                Finding(
                    severity="warning",
                    code="join_column_without_index",
                    message=f"Join column `{join_col}` on {table.schema_name}.{table.name} is not a leading index column.",
                    suggestion="Add or use an index whose first column is the join key.",
                )
            )


def _table_names(statement: exp.Expression) -> list[str]:
    names = []
    for table in statement.find_all(exp.Table):
        if table.db:
            names.append(f"{table.db}.{table.name}")
        else:
            names.append(table.name)
    return names


def _predicate_columns(statement: exp.Expression) -> set[str]:
    columns: set[str] = set()
    where = statement.args.get("where")
    if not where:
        return columns
    for col in where.find_all(exp.Column):
        columns.add(col.name.lower())
    return columns


def _join_columns(statement: exp.Expression) -> set[str]:
    columns: set[str] = set()
    for join in statement.find_all(exp.Join):
        on_expr = join.args.get("on")
        if not on_expr:
            continue
        for col in on_expr.find_all(exp.Column):
            columns.add(col.name.lower())
    return columns


def _order_columns(statement: exp.Expression) -> list[str]:
    order = statement.args.get("order")
    if not order:
        return []
    return [col.name.lower() for col in order.find_all(exp.Column)]


def _limit_offset(statement: exp.Expression, raw_sql: str) -> int | None:
    # MySQL LIMIT offset,count can be normalized by parsers, so check raw SQL first.
    match = re.search(r"\blimit\s+(\d+)\s*,\s*\d+", raw_sql, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    limit = statement.args.get("limit")
    if not limit:
        return None
    offset = limit.args.get("offset")
    if isinstance(offset, exp.Literal) and offset.is_int:
        return int(offset.name)
    text = statement.sql(dialect="mysql")
    match = re.search(r"\blimit\s+(\d+)\s*,\s*\d+", text, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _matched_indexes(table: TableInfo, predicates: set[str], order_columns: list[str]) -> list[str]:
    matched = []
    for index in table.indexes:
        cols = [c.lower() for c in index.column_names]
        if not cols:
            continue
        if cols[0] in predicates:
            matched.append(index.name)
            continue
        if order_columns and cols[: len(order_columns)] == order_columns:
            matched.append(index.name)
    return matched


def _has_index_starting_with(table: TableInfo, column: str) -> bool:
    return any(index.column_names and index.column_names[0].lower() == column.lower() for index in table.indexes)


def _review_like_prefix(sql: str, findings: list[Finding]) -> None:
    if re.search(r"\blike\s+['\"]%", sql, flags=re.IGNORECASE):
        findings.append(
            Finding(
                severity="warning",
                code="leading_wildcard_like",
                message="Query uses LIKE with a leading wildcard.",
                suggestion="A leading wildcard usually prevents normal btree index usage.",
            )
        )


def _review_index_functions(statement: exp.Expression, tables: list[TableInfo], findings: list[Finding]) -> None:
    indexed_cols = {
        col.lower()
        for table in tables
        for index in table.indexes
        for col in index.column_names
    }
    seen: set[tuple[str, str]] = set()
    ignored = {"and", "or", "eq", "neq", "gt", "gte", "lt", "lte", "in", "like", "is"}
    for func in statement.find_all(exp.Func):
        if func.key.lower() in ignored:
            continue
        for col in func.find_all(exp.Column):
            if col.name.lower() in indexed_cols:
                marker = (func.key.lower(), col.name.lower())
                if marker in seen:
                    continue
                seen.add(marker)
                findings.append(
                    Finding(
                        severity="warning",
                        code="function_on_indexed_column",
                        message=f"Function `{func.key}` is applied to indexed column `{col.name}`.",
                        suggestion="Rewrite the predicate to keep the indexed column bare when possible.",
                    )
                )

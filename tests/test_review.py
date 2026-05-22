from dbctx.config import RulesConfig
from dbctx.models import ColumnInfo, DatabaseSnapshot, IndexColumn, IndexInfo, SnapshotSource, TableInfo
from dbctx.review import review_sql


def snapshot() -> DatabaseSnapshot:
    table = TableInfo(
        schema_name="order_db",
        name="orders",
        comment="orders",
        row_count=20_000_000,
        columns=[
            ColumnInfo(name="id", type="bigint", nullable=False, ordinal=1),
            ColumnInfo(name="tenant_id", type="bigint", nullable=False, ordinal=2),
            ColumnInfo(name="user_id", type="bigint", nullable=False, ordinal=3),
            ColumnInfo(name="status", type="tinyint", nullable=False, ordinal=4),
            ColumnInfo(name="deleted", type="tinyint", nullable=False, ordinal=5),
            ColumnInfo(name="created_at", type="datetime", nullable=False, ordinal=6),
        ],
        indexes=[
            IndexInfo(name="PRIMARY", unique=True, columns=[IndexColumn(name="id", seq=1)]),
            IndexInfo(
                name="idx_tenant_user_created",
                unique=False,
                columns=[
                    IndexColumn(name="tenant_id", seq=1),
                    IndexColumn(name="user_id", seq=2),
                    IndexColumn(name="created_at", seq=3),
                ],
            ),
        ],
    )
    return DatabaseSnapshot(
        source=SnapshotSource(connection="prod_snapshot", schema_name="order_db"),
        tables={"order_db.orders": table},
    )


def test_review_flags_select_star_and_missing_filters():
    result = review_sql("select * from orders", snapshot(), RulesConfig(), "order_db")
    codes = {finding.code for finding in result.findings}
    assert result.risk == "high"
    assert "select_star" in codes
    assert "large_table_without_predicate" in codes


def test_review_matches_index_for_selective_query():
    result = review_sql(
        "select id from orders where tenant_id = 1 and user_id = 2 and deleted = 0 order by created_at desc limit 20",
        snapshot(),
        RulesConfig(),
        "order_db",
    )
    assert "idx_tenant_user_created" in result.matched_indexes
    assert all(f.severity != "error" for f in result.findings)


def test_review_flags_deep_offset():
    result = review_sql(
        "select id from orders where tenant_id = 1 limit 10000, 20",
        snapshot(),
        RulesConfig(deep_offset_threshold=1000),
        "order_db",
    )
    assert any(f.code == "deep_offset_pagination" for f in result.findings)


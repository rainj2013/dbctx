# dbctx Agent 使用说明

`dbctx` 为 AI Coding Agent 提供数据库结构、索引和表规模上下文，避免 Agent 在不了解真实数据库的情况下编写 SQL。

推荐初始化：

```bash
dbctx init
export DBCTX_PROD_SNAPSHOT_DSN='readonly:password@tcp(prod-ro:3306)/app_db'
dbctx snapshot --conn prod_snapshot
```

可选配置测试库验证：

```bash
export DBCTX_TEST_VERIFY_DSN='readonly:password@tcp(test-db:3306)/app_db'
dbctx explain --conn test_verify --sql "select id from orders where user_id = 1"
```

AI Agent 应优先使用本地 snapshot 执行 `schema`、`indexes`、`stats` 和 `review`。只有配置了只读测试库时，才使用 `explain`。


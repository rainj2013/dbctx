# dbctx CLI 参考

## 发现和自检

```bash
dbctx --help
dbctx guide
dbctx doctor
```

## 生成快照

```bash
dbctx snapshot --conn prod_snapshot
```

该命令从 MySQL `information_schema` 生成 `.dbctx/snapshot.json`。快照只包含元数据和统计信息，不包含真实业务行数据。

## 查询上下文

```bash
dbctx tables --search order
dbctx schema orders
dbctx indexes orders
dbctx stats orders
```

需要结构化输出时使用 `--format json`。

## SQL 审查

```bash
dbctx review --sql "select * from orders order by created_at limit 10000, 20"
```

`review` 是离线预检，只依赖 `.dbctx/snapshot.json`。它会输出规则 finding，也会输出表规模、索引、谓词列、排序列等上下文，供 Agent 继续做 LLM 审查。

dbctx CLI 不单独接 LLM。作为 Skill 使用时，Agent 应该把 `review` 输出当成事实输入，结合业务语义继续判断 SQL 是否合理。

退出码：

- `0`：没有高风险问题
- `2`：存在高风险问题

## EXPLAIN

```bash
dbctx explain --conn test_verify --sql "select id from orders where tenant_id = 1"
```

`explain` 在只读测试/验证库上执行，用于验证 SQL 语法、兼容性和测试库执行计划。

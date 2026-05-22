---
name: dbctx
description: 当后端编码任务涉及 SQL、数据库表结构、DAO/Repository/Mapper、ORM 查询、migration、分页、JOIN、批量写入、删除、慢查询或数据库性能问题时使用。通过 dbctx CLI 查看生产级数据库快照并在完成代码前审查 SQL 风险。
metadata:
  short-description: 后端数据库上下文审查
---

# dbctx

当任务会改变数据库读写行为时，使用 `dbctx`。

## 触发条件

涉及以下内容时运行 `dbctx`：

- SQL 文件或内联 SQL
- Mapper XML
- DAO、Repository、持久化 Adapter 或 ORM 查询构造器
- 创建或修改表/索引的 migration
- 分页、过滤、排序、JOIN、批量写入、删除或更新
- 慢查询、超时、锁、死锁或数据库性能问题

以下情况跳过：

- 纯 Controller/Service 重构
- 只改 DTO、注释、文档
- 纯前端改动
- 明确不影响数据库读写路径的代码

## 工作流

1. 从代码、SQL、Mapper 或 migration 中识别受影响表。
2. 对每张表查看上下文：
   - `dbctx schema <table>`
   - `dbctx indexes <table>`
   - `dbctx stats <table>`
3. 对每条新增或修改后的 SQL 执行：
   - `dbctx review --sql "<sql>"`
4. 如果配置了验证库，执行：
   - `dbctx explain --conn test_verify --sql "<sql>"`
5. 完成前修复所有 `error` 和高风险 SQL。保留 warning 时说明原因。

## 动态 SQL

对于 MyBatis XML、ORM 查询构造器或条件 SQL，先构造代表性 SQL：

- 最少过滤条件
- 常见过滤条件
- 查询范围最宽路径
- 分页排序路径
- JOIN 较多路径

然后对每个有意义的变体运行 `dbctx review --sql`。

## 环境区别

snapshot 通常来自生产/准生产元数据，用于判断生产风险。
`explain` 通常运行在测试/验证库，用于验证 SQL 语法、兼容性和测试库执行计划。测试库执行计划不等于生产性能结论。


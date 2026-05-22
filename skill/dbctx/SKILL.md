---
name: dbctx
description: 当后端编码任务涉及 SQL、数据库表结构、DAO/Repository/Mapper、ORM 查询、migration、分页、JOIN、批量写入、删除、慢查询或数据库性能问题时使用。通过 dbctx CLI 查看生产级数据库快照并在完成代码前审查 SQL 风险。
metadata:
  short-description: 后端数据库上下文审查
---

# dbctx

使用本 Skill，让 AI Coding Agent 在修改后端数据库读写代码时主动调用 `dbctx` CLI。

## 工具发现

开始数据库相关工作前，先找到可用的 `dbctx` 命令：

1. 先尝试 `dbctx --help`。
2. 如果不可用且安装了 `uv`，尝试 `uvx dbctx --help`。
3. 如果正在 `dbctx` 源码仓库内工作，使用 `uv run --project /path/to/dbctx dbctx ...`。
4. 如果没有任何命令可用，告诉用户 `dbctx` 未安装，不要凭空猜测数据库结构或索引。

可运行 `dbctx guide` 查看最短工作流。

## 何时使用

遇到以下任务时使用 `dbctx`：

- SQL 文件或代码中的内联 SQL
- MyBatis Mapper XML、JPA、QueryDSL、MyBatis Plus 或其他 ORM 查询
- DAO、Repository、持久化 Adapter、数据访问层代码
- 创建或修改表/索引的 migration
- 分页、过滤、排序、JOIN、批量写入、删除、更新
- 慢查询、超时、锁、死锁或数据库性能问题

以下情况可以跳过：

- 纯 Controller/Service 重构
- 只改 DTO、注释、文档
- 纯前端改动
- 明确不影响数据库读写路径的代码

## 必须流程

1. 从 SQL、代码、Mapper XML、migration 或命名中识别受影响表。
2. 对每张受影响表查看上下文：
   - `dbctx schema <table>`
   - `dbctx indexes <table>`
   - `dbctx stats <table>`
3. 对每条新增或修改后的具体 SQL 执行 dbctx 预检：
   - `dbctx review --sql "<sql>"`
4. 如果配置了测试验证库，再执行：
   - `dbctx explain --conn test_verify --sql "<sql>"`
5. 基于 `review` 输出的表规模、索引、谓词列、排序列、规则 finding，以及可选 `explain` 结果，自己完成最终 SQL 审查。不要把 `dbctx review` 当成完整优化器；它是确定性事实采集和预检。
6. 在完成任务前，必须修复所有明确的 `error` 级别问题和高风险 SQL。保留 warning 时，需要说明项目语义、数据量或索引行为上的理由。

## 动态 SQL

对于 Mapper XML 或 ORM 拼出来的动态 SQL，先构造有代表性的具体 SQL 再审查：

- 最少过滤条件
- 常见过滤条件
- 查询范围最宽的路径
- 分页和排序路径
- JOIN 较多的路径

对每个有意义的变体执行 `dbctx review --sql`。

## LLM 审查职责

dbctx CLI 不单独接 LLM，因为 Skill 本身就在 LLM Agent 环境里运行。CLI 负责给出真实数据库事实和基础规则信号，Agent 负责结合业务语义判断：

- 谓词列是否有足够选择性。
- 联合索引顺序是否匹配当前查询路径。
- `tenant_id`、`deleted` 等字段在当前业务语义下是否必须出现。
- `ORDER BY` 和分页方式在表规模下是否可接受。
- 测试库 `EXPLAIN` 是否能代表生产数据分布。
- 是否需要修改 SQL、补索引、调整分页方式，或说明保留 warning 的原因。

## 环境模型

区分 snapshot 和 explain 的含义：

- snapshot 通常来自生产/准生产只读元数据，用于判断生产风险。
- explain 通常运行在测试/开发只读库，用于验证 SQL 语法、兼容性和测试库执行计划。
- 测试库执行计划不能证明生产性能，因为数据量和统计信息可能不同。

## 更多说明

需要安装、发布或环境配置时，读取 `references/setup.md`。
需要命令细节和输出约定时，读取 `references/cli.md`。

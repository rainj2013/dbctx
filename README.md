# dbctx

`dbctx` 是一个面向 AI Coding Agent 的数据库上下文 Skill。

它解决的问题是：AI 在开发后端服务时，经常需要修改 SQL、DAO、Repository、Mapper、ORM 查询或 migration，但它通常并不知道真实数据库的表结构、索引、数据量级和查询风险。结果就是 AI 可能写出能编译、但在真实数据库上性能很差甚至不可运行的代码。

`dbctx` 通过 **Skill + CLI** 的方式，让 Codex、Claude Code 等编码 Agent 在动数据库代码前，先查询真实数据库上下文，再审查 SQL。

```text
dbctx Skill = 告诉 AI Agent 什么时候、如何使用数据库上下文
dbctx CLI   = 提供 schema / indexes / stats / review / explain 等确定性能力
```

## 它解决什么问题

在后端微服务项目中，AI Coding Agent 常见的问题包括：

- 不知道表有哪些字段，凭记忆或命名猜 SQL。
- 不知道联合索引顺序，写出的 WHERE / ORDER BY 无法有效命中索引。
- 不知道表数据量，把小表写法用到千万级大表上。
- 不知道项目里有 `tenant_id`、`deleted`、`is_deleted` 等约定字段。
- 不知道分页查询是否存在深分页风险。
- 只能在本地看代码，无法判断 SQL 是否能被真实 MySQL 解析和规划。

`dbctx` 的目标不是替代 DBA，也不是自动优化所有 SQL，而是给 AI 一个稳定的工作流：

```text
识别受影响表
  -> 查看 schema / indexes / stats
  -> 编写或修改 SQL
  -> 离线 review
  -> 可选连接测试库 explain
  -> 根据结果修正代码
```

## 工作原理

推荐把数据库环境拆成两个角色：

```text
生产/准生产只读库 -> 生成 snapshot，提供真实表结构、索引、数据量级
测试/开发只读库   -> 执行 EXPLAIN，验证 SQL 可解析、可规划
```

### 1. 生成本地快照

`dbctx snapshot` 连接生产或准生产只读库，读取 MySQL `information_schema`，生成：

```text
.dbctx/snapshot.json
```

快照包含：

- 表名、表注释
- 字段名、字段类型、nullable、默认值、字段注释
- 主键、唯一索引、普通索引、联合索引顺序
- 表行数估算
- 数据大小、索引大小
- 分区信息
- MySQL 版本和采集时间

快照不包含：

- 真实业务行数据
- 数据库账号密码
- 生产连接串
- 用户手机号、邮箱、身份证等敏感值

### 2. AI 日常查询本地快照

大多数命令都不连接数据库，只读 `.dbctx/snapshot.json`：

```bash
dbctx schema orders
dbctx indexes orders
dbctx stats orders
dbctx review --sql "select * from orders"
```

这样 AI 可以获得真实数据库上下文，但不需要频繁访问真实数据库。

### 3. 可选连接测试库执行 EXPLAIN

当配置了测试库只读连接后，可以执行：

```bash
dbctx explain --conn test_verify --sql "select id from orders where user_id = 1"
```

注意：测试库 `EXPLAIN` 用于验证 SQL 语法、兼容性和测试库执行计划。生产风险判断仍应以生产/准生产 snapshot 的表规模和索引信息为准。

## 目录结构

```text
dbctx/
  skill/dbctx/          # 可发布给 Codex / Claude Code 等 Agent 的 Skill
  src/dbctx/            # dbctx CLI 实现
  docs/                 # 发布和使用说明
  tests/                # 单元测试
```

可发布的 Skill 位于：

```text
skill/dbctx/
```

包含：

```text
SKILL.md
agents/openai.yaml
references/setup.md
references/cli.md
```

## 如何安装

### 方式一：把 GitHub 链接交给 AI Agent 安装 Skill

如果你的 Agent 支持从 GitHub 安装 Skill，可以把仓库中的 Skill 路径发给它：

```text
https://github.com/<org>/dbctx/tree/main/skill/dbctx
```

对 Codex 这类支持 Skill 安装的 Agent，可以让它安装这个路径下的 Skill。

安装后，Agent 会在涉及数据库读写代码时自动触发 `dbctx` 工作流。

### 方式二：手动复制 Skill

把目录复制到 Agent 的 Skill 目录：

```text
skill/dbctx/
```

例如 Codex 风格的目录通常类似：

```text
~/.codex/skills/dbctx/
```

复制后重启 Agent，让它重新加载 Skill。

### 方式三：安装 CLI

Skill 负责告诉 AI 什么时候使用 `dbctx`，但真正执行数据库分析的是 CLI。

开发阶段可以在本仓库中运行：

```bash
uv run dbctx --help
```

从本地源码运行：

```bash
uv run --project /path/to/dbctx dbctx --help
```

从 GitHub 直接运行：

```bash
uvx --from git+https://github.com/<org>/dbctx dbctx --help
```

发布到 PyPI 或内部 Python 包源后：

```bash
uv tool install dbctx
dbctx --help
```

一次性运行：

```bash
uvx dbctx --help
```

## 在项目中接入

在你的后端服务仓库中执行：

```bash
dbctx init
```

它会生成：

```text
dbctx.yml
.dbctx/
skills/dbctx/SKILL.md
docs/dbctx-agent-usage.md
```

`dbctx.yml` 默认包含两个连接角色：

```yaml
connections:
  prod_snapshot:
    type: mysql
    dsn_env: DBCTX_PROD_SNAPSHOT_DSN
    readonly: true
    allow:
      - snapshot

  test_verify:
    type: mysql
    dsn_env: DBCTX_TEST_VERIFY_DSN
    readonly: true
    allow:
      - explain
```

### 生成生产/准生产快照

设置只读连接：

```bash
export DBCTX_PROD_SNAPSHOT_DSN='readonly:password@tcp(prod-ro:3306)/order_db'
```

生成快照：

```bash
dbctx snapshot --conn prod_snapshot
```

验证快照：

```bash
dbctx doctor
dbctx tables
dbctx schema orders
dbctx indexes orders
dbctx stats orders
```

### 配置测试库 EXPLAIN

设置测试库只读连接：

```bash
export DBCTX_TEST_VERIFY_DSN='readonly:password@tcp(test-db:3306)/order_db'
```

执行：

```bash
dbctx explain --conn test_verify --sql "select id from orders where user_id = 1"
```

## AI Agent 如何使用

安装 Skill 后，Agent 在以下场景会使用 `dbctx`：

- 修改 SQL
- 修改 Mapper XML
- 修改 DAO / Repository / persistence adapter
- 修改 ORM 查询构造逻辑
- 新增或修改 migration
- 处理分页、排序、过滤、JOIN
- 处理批量写入、更新、删除
- 排查慢查询、超时、锁、死锁

典型流程：

```bash
dbctx schema orders
dbctx indexes orders
dbctx stats orders
dbctx review --sql "select * from orders order by created_at limit 100000, 20"
dbctx explain --conn test_verify --sql "select id from orders where tenant_id = 1"
```

对于 MyBatis XML 或 ORM 动态 SQL，Agent 应先构造代表性 SQL：

- 最少过滤条件
- 常见过滤条件
- 查询范围最宽的路径
- 分页排序路径
- JOIN 较多的路径

然后分别执行：

```bash
dbctx review --sql "<concrete sql>"
```

## SQL Review 会检查什么

当前版本会基于本地 snapshot 做离线审查，包括：

- `SELECT *`
- 大表无过滤条件
- 大表查询未命中合适索引前缀
- 深分页
- `UPDATE` / `DELETE` 无 `WHERE`
- 缺少 `tenant_id` 过滤
- 缺少 `deleted` / `is_deleted` 过滤
- JOIN 字段不是索引前缀
- `LIKE '%xxx'` 前缀通配
- 函数包裹索引列

`dbctx review` 的退出码：

```text
0 = 没有高风险问题
2 = 存在高风险问题
```

这让它也可以用于 CI。

## 安全建议

推荐使用只读账号：

```sql
GRANT SELECT, SHOW VIEW ON <db>.* TO 'dbctx_ro'@'%';
```

建议：

- 不要把 DSN 写入 `dbctx.yml`。
- 不要提交数据库密码。
- 不要让 AI 直接访问生产写库。
- snapshot 默认不包含真实业务行数据。
- 生产风险判断以生产/准生产 snapshot 为准。
- 测试库 `EXPLAIN` 只用于验证 SQL 可运行和观察测试库计划。

## 当前范围

当前版本：

- 支持 MySQL。
- 支持 snapshot、本地 schema/index/stats 查询。
- 支持离线 SQL review。
- 支持只读测试库 `EXPLAIN`。
- 支持作为 Skill 发布给 AI Coding Agent。

暂不支持：

- PostgreSQL。
- 自动解析所有 MyBatis XML / Java / Kotlin 动态 SQL。
- 自动修改业务代码。
- 采样真实业务数据。
- 直接连接生产库执行真实查询。

## 开发

```bash
uv run pytest
uv build
```

端到端测试可以用临时 MySQL 容器验证：

```text
dbctx init
  -> dbctx snapshot
  -> dbctx schema/indexes/stats
  -> dbctx review
  -> dbctx explain
```

Skill 校验：

```bash
python3 /root/.codex/skills/.system/skill-creator/scripts/quick_validate.py skill/dbctx
```


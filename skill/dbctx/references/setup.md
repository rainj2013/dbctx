# dbctx 安装与配置

`dbctx` 是 CLI-first 的 Skill。Skill 负责判断什么时候使用工具，CLI 负责提供确定性的数据库上下文能力。

## CLI 安装方式

发布到 PyPI 或内部包源后：

```bash
uv tool install dbctx
dbctx --help
```

一次性运行：

```bash
uvx dbctx --help
```

从本地源码运行：

```bash
uv run --project /path/to/dbctx dbctx --help
```

从 GitHub 仓库运行：

```bash
uvx --from git+https://github.com/<org>/dbctx dbctx --help
```

## 项目初始化

在后端服务仓库中执行：

```bash
dbctx init
```

配置 `dbctx.yml`：

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

生成生产/准生产元数据快照：

```bash
export DBCTX_PROD_SNAPSHOT_DSN='readonly:password@tcp(prod-ro:3306)/app_db'
dbctx snapshot --conn prod_snapshot
```

可选：配置测试库 explain：

```bash
export DBCTX_TEST_VERIFY_DSN='readonly:password@tcp(test-db:3306)/app_db'
dbctx explain --conn test_verify --sql "select id from orders where user_id = 1"
```

不要把数据库密码写进 `dbctx.yml` 或 snapshot。


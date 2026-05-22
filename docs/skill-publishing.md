# 以 Skill 形式发布 dbctx

`dbctx` 的推荐发布形态是 **Skill + CLI**：

```text
skill/dbctx/  -> 发布或安装到 Codex、Claude Code 等编码 Agent
dbctx CLI     -> 通过 uv、uvx、PyPI、内部包源或 GitHub 安装
```

## 发布 Skill

发布这个目录：

```text
skill/dbctx/
```

目录内容：

```text
SKILL.md
agents/openai.yaml
references/setup.md
references/cli.md
```

对 Codex 风格的 Skill，可以用下面命令校验：

```bash
python3 /root/.codex/skills/.system/skill-creator/scripts/quick_validate.py skill/dbctx
```

对其他 Agent，可以把同一个目录复制到对应的 Skill 或自定义指令机制中。Skill 文档是 CLI-first 的，不绑定具体 Agent。

## 发布 CLI

开发阶段：

```bash
uv run dbctx --help
```

从本地源码运行：

```bash
uv run --project /path/to/dbctx dbctx --help
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

从 GitHub 运行：

```bash
uvx --from git+https://github.com/<org>/dbctx dbctx --help
```

## 推荐安装流程

1. 安装或暴露 `dbctx` CLI。
2. 把 `skill/dbctx/` 安装到编码 Agent。
3. 在每个后端服务仓库中执行：

```bash
dbctx init
```

4. 配置生产/准生产 snapshot 连接和测试库 explain 连接。
5. 生成本地数据库上下文快照：

```bash
dbctx snapshot --conn prod_snapshot
```

之后 Agent 会根据 Skill 判断什么时候调用 CLI。


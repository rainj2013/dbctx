from pathlib import Path
import os

from typer.testing import CliRunner

from dbctx.cli import app


def test_init_creates_templates(tmp_path: Path):
    runner = CliRunner()
    old = Path.cwd()
    os.chdir(tmp_path)
    try:
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        assert (tmp_path / "dbctx.yml").exists()
        assert (tmp_path / "skills" / "dbctx" / "SKILL.md").exists()
        assert (tmp_path / "docs" / "dbctx-agent-usage.md").exists()
    finally:
        os.chdir(old)


def test_guide():
    runner = CliRunner()
    result = runner.invoke(app, ["guide"])
    assert result.exit_code == 0
    assert "dbctx workflow" in result.output

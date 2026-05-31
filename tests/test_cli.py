"""Tests for main.py — CLI entrypoint commands.

Covers:
- ``migrate`` command
- ``serve`` command
- ``generate`` command
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from click.testing import CliRunner
from main import cli


class TestMigrateCommand:
    """Database migration command."""

    @patch("main.run_migrations")
    def test_migrate_success(self, mock_run: MagicMock):
        """migrate command runs successfully."""
        mock_run.return_value = None
        runner = CliRunner()
        with patch.dict("os.environ", {"DATABASE_URL": "postgresql://localhost:5432/test"}):
            result = runner.invoke(cli, ["migrate"])
        assert result.exit_code == 0
        assert "Migrations complete" in result.output

    def test_migrate_fails_without_database_url(self):
        """migrate command fails when DATABASE_URL is not set."""
        runner = CliRunner()
        with patch.dict("os.environ", {}, clear=True):
            result = runner.invoke(cli, ["migrate"])
        assert result.exit_code != 0
        assert "DATABASE_URL" in result.output


class TestServeCommand:
    """Server start command."""

    @patch("main.uvicorn.run")
    def test_serve_defaults(self, mock_uvicorn: MagicMock):
        """serve command starts with default host/port."""
        runner = CliRunner()
        result = runner.invoke(cli, ["serve"])
        assert result.exit_code == 0
        mock_uvicorn.assert_called_once_with(
            "app.main:app",
            host="0.0.0.0",
            port=8000,
            reload=False,
        )

    @patch("main.uvicorn.run")
    def test_serve_custom_port(self, mock_uvicorn: MagicMock):
        """serve command accepts custom port."""
        runner = CliRunner()
        result = runner.invoke(cli, ["serve", "--port", "9000"])
        assert result.exit_code == 0
        mock_uvicorn.assert_called_once_with(
            "app.main:app",
            host="0.0.0.0",
            port=9000,
            reload=False,
        )

    @patch("main.uvicorn.run")
    def test_serve_with_reload(self, mock_uvicorn: MagicMock):
        """serve command accepts --reload flag."""
        runner = CliRunner()
        result = runner.invoke(cli, ["serve", "--reload"])
        assert result.exit_code == 0
        mock_uvicorn.assert_called_once_with(
            "app.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
        )


class TestGenerateCommand:
    """Manual pipeline execution command."""

    @patch("main.run_pipeline")
    @patch("main.load_config")
    @patch("main.OpenRouterClient")
    @patch("main.init_pool")
    @patch("main.get_pool")
    @patch("main.close_pool")
    def test_generate_success(
        self,
        mock_close: MagicMock,
        mock_get_pool: MagicMock,
        mock_init: MagicMock,
        mock_client: MagicMock,
        mock_load: MagicMock,
        mock_pipeline: MagicMock,
    ):
        """generate command runs pipeline successfully."""
        mock_pipeline.return_value = {
            "status": "completed",
            "trend": "air fryer recipes",
            "theme": "Crispy Cooking",
            "platforms": ["pinterest"],
            "options_generated": 3,
        }

        runner = CliRunner()
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test_key", "DATABASE_URL": "postgresql://localhost:5432/test"}):
            result = runner.invoke(cli, ["generate"])

        assert result.exit_code == 0
        assert "Pipeline complete" in result.output

    @patch("main.init_pool")
    def test_generate_fails_without_api_key(self, mock_init: MagicMock):
        """generate command fails when OPENROUTER_API_KEY is not set."""
        runner = CliRunner()
        with patch.dict("os.environ", {"DATABASE_URL": "postgresql://localhost:5432/test"}, clear=True):
            result = runner.invoke(cli, ["generate"])
        assert result.exit_code != 0
        assert "OPENROUTER_API_KEY" in result.output


class TestCLI:
    """General CLI tests."""

    def test_help(self):
        """CLI shows help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Did You Know" in result.output
        assert "migrate" in result.output
        assert "serve" in result.output
        assert "generate" in result.output

    def test_no_command_shows_help(self):
        """CLI without command shows help."""
        runner = CliRunner()
        result = runner.invoke(cli, [])
        assert result.exit_code == 0
        assert "Usage:" in result.output

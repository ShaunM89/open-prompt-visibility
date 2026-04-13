"""Tests for tracker suspend/resume and SIGINT handling."""

import json
import signal
import threading
import time
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from src.tracker import SuspendRun
from main import cli


class TestSuspendRunException:
    def test_is_exception(self):
        assert issubclass(SuspendRun, Exception)

    def test_can_raise_and_catch(self):
        with pytest.raises(SuspendRun):
            raise SuspendRun()


class TestResumeCLI:
    """Test the pvt resume command."""

    @patch("main.VisibilityTracker")
    def test_resume_no_suspended_runs(self, mock_cls, tmp_path):
        config = str(tmp_path / "default.yaml")
        with open(config, "w") as f:
            f.write("tool: tool/config.yaml\nusers: users\n")

        mock_tracker = MagicMock()
        mock_tracker.config = {
            "models": [],
            "brands": [],
            "prompts": {},
            "tracking": {},
            "output": {"database_path": str(tmp_path / "test.db")},
        }
        mock_tracker.db.get_suspended_runs.return_value = []
        mock_cls.return_value = mock_tracker

        runner = CliRunner()
        result = runner.invoke(cli, ["resume", "--config", config])
        assert "No resumable runs" in result.output

    @patch("main.VisibilityTracker")
    def test_resume_latest_no_suspended(self, mock_cls, tmp_path):
        config = str(tmp_path / "default.yaml")
        with open(config, "w") as f:
            f.write("tool: tool/config.yaml\nusers: users\n")

        mock_tracker = MagicMock()
        mock_tracker.config = {
            "models": [],
            "brands": [],
            "prompts": {},
            "tracking": {},
            "output": {"database_path": str(tmp_path / "test.db")},
        }
        mock_tracker.db.get_latest_suspended_run.return_value = None
        mock_cls.return_value = mock_tracker

        runner = CliRunner()
        result = runner.invoke(cli, ["resume", "--latest", "--config", config])
        assert "No resumable runs" in result.output

    @patch("main.VisibilityTracker")
    def test_resume_lists_suspended(self, mock_cls, tmp_path):
        config = str(tmp_path / "default.yaml")
        with open(config, "w") as f:
            f.write("tool: tool/config.yaml\nusers: users\n")

        mock_tracker = MagicMock()
        mock_tracker.config = {
            "models": [],
            "brands": [],
            "prompts": {},
            "tracking": {},
            "output": {"database_path": str(tmp_path / "test.db")},
        }
        mock_tracker.db.get_suspended_runs.return_value = [
            {"id": 5, "record_count": 42, "checkpoint_at": "2026-04-13"},
        ]
        mock_cls.return_value = mock_tracker

        runner = CliRunner()
        result = runner.invoke(cli, ["resume", "--config", config])
        assert "#5" in result.output
        assert "42 queries" in result.output


class TestEstimateCostCLI:
    """Test the pvt run --estimate-cost flag."""

    @patch("main.VisibilityTracker")
    def test_estimate_cost_local_model(self, mock_cls, tmp_path):
        config = str(tmp_path / "default.yaml")
        with open(config, "w") as f:
            f.write("tool: tool/config.yaml\nusers: users\n")

        mock_tracker = MagicMock()
        mock_tracker.config = {
            "models": [
                {"provider": "ollama", "model": "gemma4:e2b", "enabled": True},
            ],
            "brands": [],
            "prompts": {},
            "tracking": {
                "queries_per_prompt": 10,
                "adaptive_sampling": {"enabled": True, "max_queries": 200},
            },
            "output": {},
        }
        mock_tracker._prepare_prompts.return_value = {"brand_mentions": ["p1"] * 10}
        mock_cls.return_value = mock_tracker

        runner = CliRunner()
        result = runner.invoke(cli, ["run", "--config", config, "--estimate-cost"])
        assert result.exit_code == 0
        assert "Cost Estimate" in result.output
        assert "$0.00" in result.output

    @patch("main.VisibilityTracker")
    def test_estimate_cost_cloud_model(self, mock_cls, tmp_path):
        config = str(tmp_path / "default.yaml")
        with open(config, "w") as f:
            f.write("tool: tool/config.yaml\nusers: users\n")

        mock_tracker = MagicMock()
        mock_tracker.config = {
            "models": [
                {"provider": "openai", "model": "gpt-4o-mini", "enabled": True},
            ],
            "brands": [],
            "prompts": {},
            "tracking": {
                "queries_per_prompt": 10,
                "adaptive_sampling": {"enabled": True, "max_queries": 200},
            },
            "output": {},
        }
        mock_tracker._prepare_prompts.return_value = {"brand_mentions": ["p1"] * 50}
        mock_cls.return_value = mock_tracker

        runner = CliRunner()
        result = runner.invoke(cli, ["run", "--config", config, "--estimate-cost"])
        assert result.exit_code == 0
        assert "Cost Estimate" in result.output
        assert "gpt-4o-mini" in result.output

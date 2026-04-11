"""Tests for CLI model selection flags."""

import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from main import cli, _parse_model_spec


class TestParseModelSpec:
    def test_valid_spec(self):
        provider, model = _parse_model_spec("ollama:gemma4:e2b")
        assert provider == "ollama"
        assert model == "gemma4:e2b"

    def test_valid_spec_openai(self):
        provider, model = _parse_model_spec("openai:gpt-4o")
        assert provider == "openai"
        assert model == "gpt-4o"

    def test_valid_spec_anthropic(self):
        provider, model = _parse_model_spec("anthropic:claude-3-sonnet-20240229")
        assert provider == "anthropic"
        assert model == "claude-3-sonnet-20240229"

    def test_invalid_no_colon(self):
        with pytest.raises(ValueError, match="Invalid model spec"):
            _parse_model_spec("nomodel")

    def test_invalid_empty_provider(self):
        with pytest.raises(ValueError, match="Invalid model spec"):
            _parse_model_spec(":gemma4:e2b")

    def test_invalid_empty_model(self):
        with pytest.raises(ValueError, match="Invalid model spec"):
            _parse_model_spec("ollama:")


class TestCLIModelOnly:
    """Test --model-only flag overrides config models."""

    @patch("main.VisibilityTracker")
    def test_model_only_overrides_config(self, mock_tracker_cls, tmp_path):
        config = str(tmp_path / "default.yaml")
        with open(config, "w") as f:
            f.write("tool: tool/config.yaml\nusers: users\n")

        mock_tracker = MagicMock()
        mock_tracker.config = {
            "models": [{"provider": "ollama", "model": "nemotron-3-nano:4b", "enabled": True}],
            "brands": [],
            "prompts": {},
            "tracking": {},
        }
        mock_tracker.adapters = {}
        mock_tracker_cls.return_value = mock_tracker

        runner = CliRunner()
        result = runner.invoke(
            cli, ["run", "--config", config, "--model-only", "ollama:gemma4:e2b", "--health-check"]
        )

        assert result.exit_code == 0
        assert mock_tracker.config["models"] == [
            {
                "provider": "ollama",
                "model": "gemma4:e2b",
                "enabled": True,
                "temperature": 0.7,
            }
        ]


class TestCLIModelAdditive:
    """Test --model flag adds to config models."""

    @patch("main.VisibilityTracker")
    def test_model_adds_to_config(self, mock_tracker_cls, tmp_path):
        config = str(tmp_path / "default.yaml")
        with open(config, "w") as f:
            f.write("tool: tool/config.yaml\nusers: users\n")

        mock_tracker = MagicMock()
        mock_tracker.config = {
            "models": [{"provider": "ollama", "model": "gemma4:e2b", "enabled": True}],
            "brands": [],
            "prompts": {},
            "tracking": {},
        }
        mock_tracker.adapters = {}
        mock_tracker_cls.return_value = mock_tracker

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["run", "--config", config, "--model", "ollama:nemotron-3-nano:4b", "--health-check"],
        )

        assert result.exit_code == 0
        models = mock_tracker.config["models"]
        assert len(models) == 2
        assert models[1]["model"] == "nemotron-3-nano:4b"


class TestCLIInvalidModelSpec:
    """Test invalid model specs produce errors."""

    @patch("main.VisibilityTracker")
    def test_invalid_model_only_spec(self, mock_tracker_cls, tmp_path):
        config = str(tmp_path / "default.yaml")
        with open(config, "w") as f:
            f.write("tool: tool/config.yaml\nusers: users\n")

        mock_tracker = MagicMock()
        mock_tracker.config = {"models": [], "brands": [], "prompts": {}, "tracking": {}}
        mock_tracker_cls.return_value = mock_tracker

        runner = CliRunner()
        result = runner.invoke(
            cli, ["run", "--config", config, "--model-only", "invalid_no_colon", "--health-check"]
        )

        assert result.exit_code == 1
        assert "Invalid model spec" in result.output

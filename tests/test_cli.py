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


class TestCLIModelsCSV:
    """Test --models comma-separated flag."""

    @patch("main.VisibilityTracker")
    def test_models_csv_adds_multiple(self, mock_tracker_cls, tmp_path):
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
            [
                "run",
                "--config",
                config,
                "--models",
                "ollama:nemotron-3-nano:4b,ollama:qwen3.5:122b",
                "--health-check",
            ],
        )

        assert result.exit_code == 0
        models = mock_tracker.config["models"]
        assert len(models) == 3  # 1 from config + 2 from --models
        assert models[1]["model"] == "nemotron-3-nano:4b"
        assert models[2]["model"] == "qwen3.5:122b"

    @patch("main.VisibilityTracker")
    def test_models_csv_single_model(self, mock_tracker_cls, tmp_path):
        config = str(tmp_path / "default.yaml")
        with open(config, "w") as f:
            f.write("tool: tool/config.yaml\nusers: users\n")

        mock_tracker = MagicMock()
        mock_tracker.config = {
            "models": [],
            "brands": [],
            "prompts": {},
            "tracking": {},
        }
        mock_tracker.adapters = {}
        mock_tracker_cls.return_value = mock_tracker

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["run", "--config", config, "--models", "ollama:single-model", "--health-check"],
        )

        assert result.exit_code == 0
        models = mock_tracker.config["models"]
        assert len(models) == 1
        assert models[0]["model"] == "single-model"

    @patch("main.VisibilityTracker")
    def test_models_and_model_both_additive(self, mock_tracker_cls, tmp_path):
        """Both --model and --models should add models independently."""
        config = str(tmp_path / "default.yaml")
        with open(config, "w") as f:
            f.write("tool: tool/config.yaml\nusers: users\n")

        mock_tracker = MagicMock()
        mock_tracker.config = {
            "models": [{"provider": "ollama", "model": "base-model", "enabled": True}],
            "brands": [],
            "prompts": {},
            "tracking": {},
        }
        mock_tracker.adapters = {}
        mock_tracker_cls.return_value = mock_tracker

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "run",
                "--config",
                config,
                "--model",
                "ollama:from-model-flag",
                "--models",
                "ollama:from-models-flag",
                "--health-check",
            ],
        )

        assert result.exit_code == 0
        models = mock_tracker.config["models"]
        assert len(models) == 3  # 1 config + 1 --model + 1 --models
        assert models[1]["model"] == "from-model-flag"
        assert models[2]["model"] == "from-models-flag"


class TestCLIEnvVars:
    """Test PVT_MODELS and PVT_DEFAULT_MODEL environment variables."""

    @patch.dict("os.environ", {"PVT_DEFAULT_MODEL": "ollama:env-default-model"})
    @patch("main.VisibilityTracker")
    def test_pvt_default_model_override(self, mock_tracker_cls, tmp_path):
        config = str(tmp_path / "default.yaml")
        with open(config, "w") as f:
            f.write("tool: tool/config.yaml\nusers: users\n")

        mock_tracker = MagicMock()
        mock_tracker.config = {
            "models": [{"provider": "ollama", "model": "config-model", "enabled": True}],
            "brands": [],
            "prompts": {},
            "tracking": {},
        }
        mock_tracker.adapters = {}
        mock_tracker_cls.return_value = mock_tracker

        runner = CliRunner()
        result = runner.invoke(cli, ["run", "--config", config, "--health-check"])

        assert result.exit_code == 0
        assert mock_tracker.config["models"] == [
            {
                "provider": "ollama",
                "model": "env-default-model",
                "enabled": True,
                "temperature": 0.7,
            }
        ]

    @patch.dict("os.environ", {"PVT_MODELS": "ollama:env-add1,ollama:env-add2"})
    @patch("main.VisibilityTracker")
    def test_pvt_models_adds(self, mock_tracker_cls, tmp_path):
        config = str(tmp_path / "default.yaml")
        with open(config, "w") as f:
            f.write("tool: tool/config.yaml\nusers: users\n")

        mock_tracker = MagicMock()
        mock_tracker.config = {
            "models": [{"provider": "ollama", "model": "base-model", "enabled": True}],
            "brands": [],
            "prompts": {},
            "tracking": {},
        }
        mock_tracker.adapters = {}
        mock_tracker_cls.return_value = mock_tracker

        runner = CliRunner()
        result = runner.invoke(cli, ["run", "--config", config, "--health-check"])

        assert result.exit_code == 0
        models = mock_tracker.config["models"]
        assert len(models) == 3  # 1 from config + 2 from PVT_MODELS
        assert models[1]["model"] == "env-add1"
        assert models[2]["model"] == "env-add2"

    @patch.dict("os.environ", {"PVT_DEFAULT_MODEL": "ollama:env-model"})
    @patch("main.VisibilityTracker")
    def test_cli_model_only_overrides_env(self, mock_tracker_cls, tmp_path):
        """CLI --model-only should take precedence over PVT_DEFAULT_MODEL."""
        config = str(tmp_path / "default.yaml")
        with open(config, "w") as f:
            f.write("tool: tool/config.yaml\nusers: users\n")

        mock_tracker = MagicMock()
        mock_tracker.config = {
            "models": [],
            "brands": [],
            "prompts": {},
            "tracking": {},
        }
        mock_tracker.adapters = {}
        mock_tracker_cls.return_value = mock_tracker

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["run", "--config", config, "--model-only", "ollama:cli-model", "--health-check"],
        )

        assert result.exit_code == 0
        assert mock_tracker.config["models"] == [
            {"provider": "ollama", "model": "cli-model", "enabled": True, "temperature": 0.7}
        ]


class TestCLIScenario:
    """Test --scenario flag."""

    @patch("main.VisibilityTracker")
    def test_scenario_replaces_models(self, mock_tracker_cls, tmp_path):
        config = str(tmp_path / "default.yaml")
        with open(config, "w") as f:
            f.write("tool: tool/config.yaml\nusers: users\n")

        scenario_models = [
            {"provider": "ollama", "model": "scenario-model", "enabled": True, "temperature": 0.7}
        ]
        mock_tracker = MagicMock()
        mock_tracker.config = {
            "models": [{"provider": "ollama", "model": "config-model", "enabled": True}],
            "scenarios": {"my_scenario": {"models": scenario_models}},
            "brands": [],
            "prompts": {},
            "tracking": {},
        }
        mock_tracker.adapters = {}
        mock_tracker_cls.return_value = mock_tracker

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["run", "--config", config, "--scenario", "my_scenario", "--health-check"],
        )

        assert result.exit_code == 0
        assert mock_tracker.config["models"] == scenario_models

    @patch("main.VisibilityTracker")
    def test_invalid_scenario_error(self, mock_tracker_cls, tmp_path):
        config = str(tmp_path / "default.yaml")
        with open(config, "w") as f:
            f.write("tool: tool/config.yaml\nusers: users\n")

        mock_tracker = MagicMock()
        mock_tracker.config = {
            "models": [],
            "scenarios": {},
            "brands": [],
            "prompts": {},
            "tracking": {},
        }
        mock_tracker.adapters = {}
        mock_tracker_cls.return_value = mock_tracker

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["run", "--config", config, "--scenario", "nonexistent", "--health-check"],
        )

        assert result.exit_code == 1
        assert "not found" in result.output

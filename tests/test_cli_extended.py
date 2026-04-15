"""Tests for extended CLI commands: export, stats, trends, serve, run flags."""

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from main import cli


def _write_minimal_config(path):
    with open(path, "w") as f:
        f.write("tool: tool/config.yaml\nusers: users\n")


class TestExportCLI:
    @patch("main.VisibilityTracker")
    def test_export_csv(self, mock_tracker_cls, tmp_path):
        mock_tracker = MagicMock()
        mock_tracker.export_results.return_value = str(tmp_path / "out.csv")
        mock_tracker_cls.return_value = mock_tracker

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "export",
                "--format",
                "csv",
                "--output",
                str(tmp_path / "out.csv"),
            ],
        )
        assert result.exit_code == 0
        assert "Exported" in result.output

    @patch("main.VisibilityTracker")
    def test_export_json(self, mock_tracker_cls, tmp_path):
        mock_tracker = MagicMock()
        mock_tracker.export_results.return_value = str(tmp_path / "out.json")
        mock_tracker_cls.return_value = mock_tracker

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "export",
                "--format",
                "json",
                "--output",
                str(tmp_path / "out.json"),
            ],
        )
        assert result.exit_code == 0


class TestStatsCLI:
    @patch("main.TrackDatabase")
    def test_stats_command(self, mock_db_cls):
        mock_db = MagicMock()
        mock_db.get_stats.return_value = {
            "total_runs": 5,
            "total_records": 100,
            "unique_models": 2,
            "total_mentions": 40,
        }
        mock_db_cls.return_value = mock_db

        runner = CliRunner()
        result = runner.invoke(cli, ["stats"])
        assert result.exit_code == 0
        assert "100" in result.output


class TestServeCLI:
    @patch("uvicorn.run")
    def test_serve_command(self, mock_run):
        runner = CliRunner()
        result = runner.invoke(cli, ["serve", "--port", "8001"])
        mock_run.assert_called_once()
        assert result.exit_code == 0


class TestRunEstimateCost:
    @patch("main.VisibilityTracker")
    def test_estimate_cost_flag(self, mock_tracker_cls, tmp_path):
        config = str(tmp_path / "default.yaml")
        _write_minimal_config(config)

        mock_tracker = MagicMock()
        mock_tracker.config = {
            "models": [{"provider": "ollama", "model": "test", "enabled": True}],
            "brands": [],
            "prompts": {"test": ["p1"]},
            "tracking": {"queries_per_prompt": 5, "adaptive_sampling": {"max_queries": 50}},
        }
        mock_tracker.adapters = {}
        mock_tracker._prepare_prompts.return_value = {"test": ["p1"]}
        mock_tracker_cls.return_value = mock_tracker

        runner = CliRunner()
        result = runner.invoke(cli, ["run", "--config", config, "--estimate-cost"])
        assert result.exit_code == 0
        assert "Cost Estimate" in result.output


class TestRunVariationFlags:
    @patch("main.VisibilityTracker")
    def test_enable_variations_flag(self, mock_tracker_cls, tmp_path):
        config = str(tmp_path / "default.yaml")
        _write_minimal_config(config)

        mock_tracker = MagicMock()
        mock_tracker.config = {
            "models": [{"provider": "ollama", "model": "test", "enabled": True}],
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
                "--enable-variations",
                "--health-check",
            ],
        )
        assert result.exit_code == 0
        tracking = mock_tracker.config["tracking"]
        assert tracking["prompt_variations"]["enabled"] is True


class TestRunAdaptiveFlags:
    @patch("main.VisibilityTracker")
    def test_target_ci_width(self, mock_tracker_cls, tmp_path):
        config = str(tmp_path / "default.yaml")
        _write_minimal_config(config)

        mock_tracker = MagicMock()
        mock_tracker.config = {
            "models": [{"provider": "ollama", "model": "test", "enabled": True}],
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
                "--target-ci-width",
                "15.0",
                "--health-check",
            ],
        )
        assert result.exit_code == 0
        assert mock_tracker.config["tracking"]["adaptive_sampling"]["target_ci_width"] == 15.0

    @patch("main.VisibilityTracker")
    def test_max_queries_flag(self, mock_tracker_cls, tmp_path):
        config = str(tmp_path / "default.yaml")
        _write_minimal_config(config)

        mock_tracker = MagicMock()
        mock_tracker.config = {
            "models": [{"provider": "ollama", "model": "test", "enabled": True}],
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
                "--max-queries",
                "100",
                "--health-check",
            ],
        )
        assert result.exit_code == 0
        assert mock_tracker.config["tracking"]["adaptive_sampling"]["max_queries"] == 100

    @patch("main.VisibilityTracker")
    def test_convergence_scope_flag(self, mock_tracker_cls, tmp_path):
        config = str(tmp_path / "default.yaml")
        _write_minimal_config(config)

        mock_tracker = MagicMock()
        mock_tracker.config = {
            "models": [{"provider": "ollama", "model": "test", "enabled": True}],
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
                "--convergence-scope",
                "all_tracked_brands",
                "--health-check",
            ],
        )
        assert result.exit_code == 0
        assert (
            mock_tracker.config["tracking"]["adaptive_sampling"]["convergence_scope"]
            == "all_tracked_brands"
        )


class TestRunSentimentFlag:
    @patch("main.VisibilityTracker")
    def test_sentiment_mode_flag(self, mock_tracker_cls, tmp_path):
        config = str(tmp_path / "default.yaml")
        _write_minimal_config(config)

        mock_tracker = MagicMock()
        mock_tracker.config = {
            "models": [{"provider": "ollama", "model": "test", "enabled": True}],
            "brands": [],
            "prompts": {},
            "tracking": {},
        }
        mock_tracker.adapters = {}
        mock_tracker.sentiment_analyzer = MagicMock()
        mock_tracker_cls.return_value = mock_tracker

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "run",
                "--config",
                config,
                "--sentiment-mode",
                "off",
                "--health-check",
            ],
        )
        assert result.exit_code == 0
        assert mock_tracker.config["sentiment"]["mode"] == "off"


class TestResumeCLI:
    @patch("main.VisibilityTracker")
    def test_resume_no_suspended_runs(self, mock_tracker_cls, tmp_path):
        config = str(tmp_path / "default.yaml")
        _write_minimal_config(config)

        mock_tracker = MagicMock()
        mock_tracker.db.get_latest_suspended_run.return_value = None
        mock_tracker.db.get_suspended_runs.return_value = []
        mock_tracker_cls.return_value = mock_tracker

        runner = CliRunner()
        result = runner.invoke(cli, ["resume", "--config", config, "--latest"])
        assert result.exit_code == 0
        assert "No resumable runs" in result.output

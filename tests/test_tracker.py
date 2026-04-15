"""Tests for VisibilityTracker core methods."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from src.storage import TrackDatabase
from src.tracker import RunResult, SuspendRun, VisibilityTracker


def _make_config(**overrides):
    base = {
        "brands": [{"name": "Nike", "keywords": ["Nike"]}],
        "models": [{"provider": "ollama", "model": "test-model", "enabled": True}],
        "prompts": {"test": ["What are the best shoes?"]},
        "tracking": {"queries_per_prompt": 5, "max_retries": 2},
        "output": {"database_path": ":memory:"},
        "sentiment": {"mode": "off"},
    }
    base.update(overrides)
    return base


def _make_tracker(config, tmp_path):
    with patch.object(VisibilityTracker, "__init__", lambda self, *a, **kw: None):
        tracker = VisibilityTracker.__new__(VisibilityTracker)
        tracker.config = config
        tracker.db = TrackDatabase(str(tmp_path / "test.db"))
        tracker.adapters = {}
        tracker._prompt_metadata = {}
        tracker.config_path = str(tmp_path / "config.yaml")
        tracker.config_hash = "test_hash"
        tracker._result_lock = MagicMock()
        tracker._suspend_requested = MagicMock()
        tracker.sentiment_analyzer = None
        tracker.context_extractor = None
        tracker.detector = MagicMock()
        tracker.analyzer = MagicMock()
        tracker.generator = MagicMock()
        tracker.compiler = MagicMock()
        return tracker


class TestRunResult:
    def test_defaults(self):
        r = RunResult(run_id=1, started_at=None)
        assert r.total_queries == 0
        assert r.successful_queries == 0
        assert r.failed_queries == 0
        assert r.models_used == []
        assert r.errors == []


class TestSuspendRun:
    def test_is_exception(self):
        with pytest.raises(SuspendRun):
            raise SuspendRun()


class TestLoadConfig:
    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            VisibilityTracker(str(tmp_path / "nonexistent.yaml"))

    def test_missing_required_field_raises(self, tmp_path):
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump({"brands": []}))
        with pytest.raises(ValueError, match="Missing required config field"):
            VisibilityTracker(str(config_path))

    def test_detection_settings_merge(self, tmp_path):
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "brands": [{"name": "Nike"}],
                    "models": [{"provider": "ollama", "model": "test", "enabled": True}],
                    "prompts": {"test": ["p"]},
                    "tracking": {"queries_per_prompt": 5},
                    "output": {"database_path": str(tmp_path / "test.db")},
                    "sentiment": {"mode": "off"},
                    "detection": {"method": "keyword"},
                }
            )
        )
        with patch.object(VisibilityTracker, "_init_adapters", return_value={}):
            tracker = VisibilityTracker(str(config_path))
        assert tracker.config["tracking"]["detection_method"] == "keyword"


class TestCalculateConfigHash:
    def test_consistent_hash(self, tmp_path):
        tracker = _make_tracker(_make_config(), tmp_path)
        h1 = tracker._calculate_config_hash()
        h2 = tracker._calculate_config_hash()
        assert h1 == h2
        assert len(h1) == 16

    def test_different_config_different_hash(self, tmp_path):
        c1 = _make_config()
        c2 = _make_config(brands=[{"name": "Adidas", "keywords": ["Adidas"]}])
        t1 = _make_tracker(c1, tmp_path)
        t2 = _make_tracker(c2, tmp_path)
        assert t1._calculate_config_hash() != t2._calculate_config_hash()


class TestInitAdapters:
    def test_skips_disabled_models(self, tmp_path):
        config = _make_config()
        config["models"] = [
            {"provider": "ollama", "model": "active", "enabled": True},
            {"provider": "ollama", "model": "inactive", "enabled": False},
        ]
        tracker = _make_tracker(config, tmp_path)
        adapters = tracker._init_adapters()
        assert len(adapters) == 1
        assert "ollama:active" in adapters

    def test_skips_invalid_provider(self, tmp_path):
        config = _make_config()
        config["models"] = [
            {"provider": "ollama", "model": "ok", "enabled": True},
            {"provider": "invalid_provider", "model": "bad", "enabled": True},
        ]
        tracker = _make_tracker(config, tmp_path)
        adapters = tracker._init_adapters()
        assert len(adapters) == 1


class TestPreparePrompts:
    def test_dict_format(self, tmp_path):
        tracker = _make_tracker(_make_config(), tmp_path)
        result = tracker._prepare_prompts()
        assert "test" in result
        assert len(result["test"]) == 1

    def test_list_format(self, tmp_path):
        config = _make_config()
        config["prompts"] = [{"canonical_id": "c1", "prompts": ["p1", "p2"], "tags": {}}]
        tracker = _make_tracker(config, tmp_path)
        result = tracker._prepare_prompts()
        assert "structured" in result
        assert len(result["structured"]) == 2


class TestExportResults:
    def test_export_specific_run_json(self, tmp_path):
        tracker = _make_tracker(_make_config(), tmp_path)
        run_id = tracker.db.create_run(config_hash="test")
        tracker.db.record_query(run_id, "ollama", "m1", "p1", "Nike response", {"Nike": 1})
        output = str(tmp_path / "export.json")
        result = tracker.export_results(run_id=run_id, output_path=output)
        assert Path(result).exists()
        with open(result) as f:
            data = json.load(f)
        assert len(data) == 1

    def test_export_all_csv(self, tmp_path):
        tracker = _make_tracker(_make_config(), tmp_path)
        run_id = tracker.db.create_run(config_hash="test")
        tracker.db.record_query(run_id, "ollama", "m1", "p1", "resp", {})
        output = str(tmp_path / "export.csv")
        result = tracker.export_results(format="csv", output_path=output)
        assert Path(result).exists()

    def test_export_all_json(self, tmp_path):
        tracker = _make_tracker(_make_config(), tmp_path)
        run_id = tracker.db.create_run(config_hash="test")
        tracker.db.record_query(run_id, "ollama", "m1", "p1", "resp", {})
        output = str(tmp_path / "export.json")
        result = tracker.export_results(format="json", output_path=output)
        assert Path(result).exists()

    def test_export_invalid_format_raises(self, tmp_path):
        tracker = _make_tracker(_make_config(), tmp_path)
        with pytest.raises(ValueError, match="Unsupported format"):
            tracker.export_results(format="xml", output_path=str(tmp_path / "out.xml"))

    def test_export_nonexistent_run_raises(self, tmp_path):
        tracker = _make_tracker(_make_config(), tmp_path)
        with pytest.raises(ValueError, match="No records found"):
            tracker.export_results(run_id=99999, output_path=str(tmp_path / "out.json"))

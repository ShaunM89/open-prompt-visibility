"""Tests for run lifecycle: suspend/resume, checkpointing, status tracking."""

import json
import threading
import time

import pytest

from src.storage import TrackDatabase


class TestRunStatus:
    """Test run status column and transitions."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        db = TrackDatabase(db_path=db_path)
        yield db

    def test_create_run_default_status_running(self, temp_db):
        run_id = temp_db.create_run(config_hash="abc")
        status = temp_db.get_run_status(run_id)
        assert status == "running"

    def test_create_run_custom_status(self, temp_db):
        run_id = temp_db.create_run(config_hash="abc", status="completed")
        status = temp_db.get_run_status(run_id)
        assert status == "completed"

    def test_set_run_status(self, temp_db):
        run_id = temp_db.create_run(config_hash="abc")
        assert temp_db.get_run_status(run_id) == "running"

        temp_db.set_run_status(run_id, "suspended")
        assert temp_db.get_run_status(run_id) == "suspended"

        temp_db.set_run_status(run_id, "running")
        assert temp_db.get_run_status(run_id) == "running"

    def test_set_run_status_failed(self, temp_db):
        run_id = temp_db.create_run(config_hash="abc")
        temp_db.set_run_status(run_id, "failed")
        assert temp_db.get_run_status(run_id) == "failed"

    def test_get_run_status_nonexistent(self, temp_db):
        assert temp_db.get_run_status(9999) is None

    def test_complete_run_sets_completed_status(self, temp_db):
        run_id = temp_db.create_run(config_hash="abc")
        temp_db.complete_run(run_id)
        assert temp_db.get_run_status(run_id) == "completed"

    def test_complete_run_with_metadata_sets_completed(self, temp_db):
        run_id = temp_db.create_run(config_hash="abc")
        temp_db.complete_run(run_id, metadata={"convergence": {"pairs": 5}})
        assert temp_db.get_run_status(run_id) == "completed"


class TestCheckpointing:
    """Test checkpoint save/load cycle."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        db = TrackDatabase(db_path=db_path)
        yield db

    def test_checkpoint_round_trip(self, temp_db):
        run_id = temp_db.create_run(config_hash="abc")
        data = {
            "total_queries": 42,
            "successful_queries": 40,
            "failed_queries": 2,
            "models": ["ollama:gemma4:e2b"],
            "prompt_list": [{"category": "brand_mentions", "prompt": "Test prompt"}],
        }
        temp_db.checkpoint_run(run_id, data)

        loaded = temp_db.get_checkpoint(run_id)
        assert loaded is not None
        assert loaded["total_queries"] == 42
        assert loaded["successful_queries"] == 40
        assert loaded["failed_queries"] == 2
        assert loaded["models"] == ["ollama:gemma4:e2b"]
        assert len(loaded["prompt_list"]) == 1

    def test_checkpoint_includes_run_metadata(self, temp_db):
        run_id = temp_db.create_run(config_hash="abc")
        temp_db.checkpoint_run(run_id, {"total_queries": 10})

        loaded = temp_db.get_checkpoint(run_id)
        assert loaded["_run_status"] == "running"
        assert loaded["_started_at"] is not None

    def test_get_checkpoint_no_checkpoint(self, temp_db):
        run_id = temp_db.create_run(config_hash="abc")
        assert temp_db.get_checkpoint(run_id) is None

    def test_get_checkpoint_nonexistent_run(self, temp_db):
        assert temp_db.get_checkpoint(9999) is None

    def test_complete_run_clears_checkpoint(self, temp_db):
        run_id = temp_db.create_run(config_hash="abc")
        temp_db.checkpoint_run(run_id, {"total_queries": 10})
        assert temp_db.get_checkpoint(run_id) is not None

        temp_db.complete_run(run_id)
        assert temp_db.get_checkpoint(run_id) is None

    def test_checkpoint_overwrite(self, temp_db):
        run_id = temp_db.create_run(config_hash="abc")
        temp_db.checkpoint_run(run_id, {"total_queries": 10})
        temp_db.checkpoint_run(run_id, {"total_queries": 20})

        loaded = temp_db.get_checkpoint(run_id)
        assert loaded["total_queries"] == 20


class TestSuspendedRuns:
    """Test querying suspended runs."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        db = TrackDatabase(db_path=db_path)
        yield db

    def _make_run_with_records(self, db, n_records=5):
        run_id = db.create_run(config_hash="abc")
        for i in range(n_records):
            db.record_query(
                run_id=run_id,
                model_provider="ollama",
                model_name="gemma4:e2b",
                prompt=f"Prompt {i}",
                response_text=f"Response {i}",
                mentions={"Nike": 1} if i % 2 == 0 else {},
            )
        return run_id

    def test_get_suspended_runs_empty(self, temp_db):
        assert temp_db.get_suspended_runs() == []

    def test_get_suspended_runs_finds_suspended(self, temp_db):
        run_id = self._make_run_with_records(temp_db)
        temp_db.checkpoint_run(run_id, {"total_queries": 5, "models": [], "prompt_list": []})
        temp_db.set_run_status(run_id, "suspended")

        runs = temp_db.get_suspended_runs()
        assert len(runs) == 1
        assert runs[0]["id"] == run_id
        assert runs[0]["status"] == "suspended"
        assert runs[0]["record_count"] == 5

    def test_get_suspended_runs_includes_running_with_checkpoint(self, temp_db):
        run_id = self._make_run_with_records(temp_db)
        temp_db.checkpoint_run(run_id, {"total_queries": 5, "models": [], "prompt_list": []})
        runs = temp_db.get_suspended_runs()
        assert len(runs) == 1
        assert runs[0]["id"] == run_id

    def test_get_suspended_runs_excludes_running_without_checkpoint(self, temp_db):
        run_id = self._make_run_with_records(temp_db)
        assert temp_db.get_suspended_runs() == []

    def test_get_suspended_runs_excludes_completed(self, temp_db):
        run_id = self._make_run_with_records(temp_db)
        temp_db.complete_run(run_id)
        assert temp_db.get_suspended_runs() == []

    def test_get_latest_suspended_run(self, temp_db):
        run1 = temp_db.create_run(config_hash="a")
        run2 = temp_db.create_run(config_hash="b")

        temp_db.checkpoint_run(run1, {"models": [], "prompt_list": []})
        temp_db.set_run_status(run1, "suspended")

        temp_db.checkpoint_run(run2, {"models": [], "prompt_list": []})
        temp_db.set_run_status(run2, "suspended")

        latest = temp_db.get_latest_suspended_run()
        assert latest is not None
        assert latest["id"] == run2

    def test_get_latest_suspended_run_none(self, temp_db):
        assert temp_db.get_latest_suspended_run() is None


class TestRunQueryCounts:
    """Test per-model and per-prompt query count methods."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        db = TrackDatabase(db_path=db_path)
        yield db

    def test_get_run_query_counts_empty(self, temp_db):
        run_id = temp_db.create_run()
        assert temp_db.get_run_query_counts(run_id) == {}

    def test_get_run_query_counts(self, temp_db):
        run_id = temp_db.create_run()
        for _ in range(3):
            temp_db.record_query(run_id, "ollama", "model_a", "p1", "r", {})
        for _ in range(5):
            temp_db.record_query(run_id, "ollama", "model_b", "p1", "r", {})

        counts = temp_db.get_run_query_counts(run_id)
        assert counts == {"model_a": 3, "model_b": 5}

    def test_get_run_model_prompt_counts(self, temp_db):
        run_id = temp_db.create_run()
        temp_db.record_query(run_id, "ollama", "model_a", "prompt1", "r", {})
        temp_db.record_query(run_id, "ollama", "model_a", "prompt1", "r", {})
        temp_db.record_query(run_id, "ollama", "model_a", "prompt2", "r", {})
        temp_db.record_query(run_id, "ollama", "model_b", "prompt1", "r", {})

        counts = temp_db.get_run_model_prompt_counts(run_id)
        assert counts["model_a"]["prompt1"] == 2
        assert counts["model_a"]["prompt2"] == 1
        assert counts["model_b"]["prompt1"] == 1

    def test_get_run_model_prompt_counts_isolated(self, temp_db):
        run1 = temp_db.create_run()
        run2 = temp_db.create_run()
        temp_db.record_query(run1, "ollama", "model_a", "p1", "r", {})
        temp_db.record_query(run2, "ollama", "model_a", "p1", "r", {})
        temp_db.record_query(run2, "ollama", "model_a", "p1", "r", {})

        assert temp_db.get_run_model_prompt_counts(run1) == {"model_a": {"p1": 1}}
        assert temp_db.get_run_model_prompt_counts(run2) == {"model_a": {"p1": 2}}


class TestRunStateMachine:
    """Test the full run lifecycle: running → suspended → running → completed."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        db = TrackDatabase(db_path=db_path)
        yield db

    def test_full_lifecycle(self, temp_db):
        run_id = temp_db.create_run(config_hash="abc")
        assert temp_db.get_run_status(run_id) == "running"

        for i in range(10):
            temp_db.record_query(
                run_id, "ollama", "gemma4:e2b", f"prompt {i % 3}", "response", {"Nike": 1}
            )

        temp_db.checkpoint_run(
            run_id,
            {
                "total_queries": 10,
                "successful_queries": 10,
                "failed_queries": 0,
                "models": ["ollama:gemma4:e2b"],
                "prompt_list": [{"category": "test", "prompt": f"prompt {i}"} for i in range(3)],
            },
        )
        temp_db.set_run_status(run_id, "suspended")
        assert temp_db.get_run_status(run_id) == "suspended"

        checkpoint = temp_db.get_checkpoint(run_id)
        assert checkpoint is not None
        assert checkpoint["total_queries"] == 10

        suspended = temp_db.get_suspended_runs()
        assert len(suspended) == 1

        temp_db.set_run_status(run_id, "running")
        assert temp_db.get_run_status(run_id) == "running"
        assert len(temp_db.get_suspended_runs()) == 1

        for i in range(10, 20):
            temp_db.record_query(run_id, "ollama", "gemma4:e2b", f"prompt {i % 3}", "response", {})

        temp_db.complete_run(run_id, metadata={"convergence": {"pairs": 3}})
        assert temp_db.get_run_status(run_id) == "completed"
        assert temp_db.get_checkpoint(run_id) is None

        records = temp_db.get_by_run(run_id)
        assert len(records) == 20

"""Tests for database storage."""

import json
from pathlib import Path

import pytest

from src.storage import TrackDatabase


class TestTrackDatabase:
    """Test database operations."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary database for testing."""
        db_path = str(tmp_path / "test.db")
        db = TrackDatabase(db_path=db_path)
        yield db

    def test_init_creates_tables(self, temp_db):
        """Test that tables are created on initialization."""
        conn = temp_db._get_connection()
        cursor = conn.cursor()

        # Check runs table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='runs'")
        assert cursor.fetchone() is not None

        # Check visibility_records table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='visibility_records'"
        )
        assert cursor.fetchone() is not None

        conn.close()

    def test_create_run(self, temp_db):
        """Test creating a run record."""
        run_id = temp_db.create_run(config_hash="test123")

        assert run_id > 0

        runs = temp_db.get_recent_runs(days=30)
        assert len(runs) == 1
        assert runs[0]["config_hash"] == "test123"

    def test_record_query(self, temp_db):
        """Test recording a query result."""
        run_id = temp_db.create_run()

        record_id = temp_db.record_query(
            run_id=run_id,
            model_provider="ollama",
            model_name="qwen3.5:122b",
            prompt="Test prompt",
            response_text="Test response mentioning Nike",
            mentions={"Nike": 1},
        )

        assert record_id > 0

        records = temp_db.get_by_run(run_id)
        assert len(records) == 1
        assert records[0]["model_name"] == "qwen3.5:122b"
        assert "Nike" in records[0]["mentions_json"]

    def test_export_to_csv(self, temp_db):
        """Test CSV export."""
        run_id = temp_db.create_run()
        temp_db.record_query(
            run_id=run_id,
            model_provider="ollama",
            model_name="qwen3.5:122b",
            prompt="Test",
            response_text="Response",
            mentions={"Nike": 1},
        )

        output_path = str(temp_db.db_path.parent / "test_export.csv")
        temp_db.export_to_csv(output_path)

        assert Path(output_path).exists()

    def test_export_to_json(self, temp_db):
        """Test JSON export."""
        run_id = temp_db.create_run()
        temp_db.record_query(
            run_id=run_id,
            model_provider="ollama",
            model_name="qwen3.5:122b",
            prompt="Test",
            response_text="Response",
            mentions={"Nike": 1},
        )

        output_path = str(temp_db.db_path.parent / "test_export.json")
        temp_db.export_to_json(output_path)

        assert Path(output_path).exists()

        with open(output_path, "r") as f:
            data = json.load(f)

        assert len(data) == 1
        assert data[0]["mentions_json"] == '{"Nike": 1}'

    def test_get_stats(self, temp_db):
        """Test statistics retrieval."""
        run_id = temp_db.create_run()
        temp_db.record_query(
            run_id=run_id,
            model_provider="ollama",
            model_name="qwen3.5:122b",
            prompt="Test",
            response_text="Response",
            mentions={},
        )

        stats = temp_db.get_stats()

        assert stats["total_runs"] == 1
        assert stats["total_records"] == 1
        assert stats["unique_models"] == 1

    def test_update_record_sentiment(self, temp_db):
        run_id = temp_db.create_run()
        record_id = temp_db.record_query(
            run_id=run_id,
            model_provider="ollama",
            model_name="qwen3.5:122b",
            prompt="Test",
            response_text="Response mentioning Nike",
            mentions={"Nike": 1},
        )
        new_mentions = json.dumps({"Nike": {"count": 1, "sentiment": {"composite": 0.5}}})
        temp_db.update_record_sentiment(record_id, new_mentions)
        records = temp_db.get_by_run(run_id)
        assert "sentiment" in records[0]["mentions_json"]

    def test_get_recent_runs(self, temp_db):
        temp_db.create_run(config_hash="hash1")
        temp_db.create_run(config_hash="hash2")
        runs = temp_db.get_recent_runs(days=30)
        assert len(runs) == 2

    def test_get_recent_runs_no_results(self, temp_db):
        runs = temp_db.get_recent_runs(days=0)
        assert len(runs) == 0

    def test_get_trends_grouped_by_day(self, temp_db):
        run_id = temp_db.create_run()
        temp_db.record_query(run_id, "ollama", "model1", "p1", "Nike is great", {"Nike": 1})
        temp_db.record_query(run_id, "ollama", "model1", "p2", "No brand", {})
        trends = temp_db.get_trends("Nike", days=30, group_by_day=True)
        assert len(trends) >= 1
        assert trends[0]["total_queries"] >= 1

    def test_get_trends_grouped_by_model(self, temp_db):
        run_id = temp_db.create_run()
        temp_db.record_query(run_id, "ollama", "model1", "p1", "Nike", {"Nike": 1})
        temp_db.record_query(run_id, "ollama", "model2", "p2", "Adidas", {"Adidas": 1})
        trends = temp_db.get_trends("Nike", days=30, group_by_day=False)
        assert len(trends) >= 1

    def test_get_model_statistics(self, temp_db):
        run_id = temp_db.create_run()
        temp_db.record_query(run_id, "ollama", "model1", "p1", "Nike great", {"Nike": 1})
        temp_db.record_query(run_id, "ollama", "model1", "p2", "No brand", {})
        stats = temp_db.get_model_statistics("Nike", days=30)
        assert len(stats) == 1
        assert stats[0]["model_name"] == "model1"
        assert stats[0]["total_runs"] == 2
        assert stats[0]["total_mentions"] == 1

    def test_get_unique_brands(self, temp_db):
        run_id = temp_db.create_run()
        temp_db.record_query(run_id, "ollama", "m1", "p1", "text", {"Nike": 1})
        temp_db.record_query(run_id, "ollama", "m1", "p2", "text", {"Adidas": 2})
        brands = temp_db.get_unique_brands()
        assert "Nike" in brands
        assert "Adidas" in brands

    def test_get_unique_brands_empty(self, temp_db):
        run_id = temp_db.create_run()
        temp_db.record_query(run_id, "ollama", "m1", "p1", "text", {})
        brands = temp_db.get_unique_brands()
        assert brands == []

    def test_get_all_mentions(self, temp_db):
        run_id = temp_db.create_run()
        temp_db.record_query(run_id, "ollama", "m1", "p1", "Nike", {"Nike": 1})
        temp_db.record_query(run_id, "ollama", "m1", "p2", "No brand", {})
        mentions = temp_db.get_all_mentions(days=30)
        assert len(mentions) == 1
        assert "Nike" in mentions[0]["mentions_json"]

    def test_cleanup_old_runs_nothing_to_delete(self, temp_db):
        deleted = temp_db.cleanup_old_runs(max_days=90)
        assert deleted == 0

    def test_get_visibility_by_segment(self, temp_db):
        run_id = temp_db.create_run()
        temp_db.record_query(
            run_id,
            "ollama",
            "m1",
            "p1",
            "Nike great",
            {"Nike": 1},
            prompt_tags='{"intent": "branded", "topic": "running"}',
            canonical_id="run_001",
        )
        temp_db.record_query(
            run_id,
            "ollama",
            "m1",
            "p2",
            "Generic",
            {},
            prompt_tags='{"intent": "informational", "topic": "running"}',
            canonical_id="info_001",
        )
        segments = temp_db.get_visibility_by_segment("Nike", "intent", days=30)
        assert len(segments) == 2
        branded = [s for s in segments if s["segment_value"] == "branded"][0]
        assert branded["mention_count"] == 1
        assert branded["total_queries"] == 1

    def test_get_visibility_by_segment_empty(self, temp_db):
        segments = temp_db.get_visibility_by_segment("Nike", "intent", days=30)
        assert segments == []

    def test_get_segment_comparison(self, temp_db):
        run_id = temp_db.create_run()
        temp_db.record_query(
            run_id,
            "ollama",
            "m1",
            "p1",
            "Nike and Adidas",
            {"Nike": 1, "Adidas": 1},
            prompt_tags='{"intent": "branded"}',
        )
        comparison = temp_db.get_segment_comparison(["Nike", "Adidas"], "intent", days=30)
        assert "Nike" in comparison
        assert "Adidas" in comparison

    def test_get_variation_drift(self, temp_db):
        run_id = temp_db.create_run()
        temp_db.record_query(
            run_id,
            "ollama",
            "m1",
            "What are the best running shoes?",
            "Nike shoes response",
            {"Nike": 1},
            canonical_id="run_001",
        )
        temp_db.record_query(
            run_id,
            "ollama",
            "m1",
            "What are good running shoes?",
            "Generic response",
            {},
            canonical_id="run_001",
        )
        drift = temp_db.get_variation_drift("run_001", "Nike", days=30)
        assert len(drift) == 2
        rates = sorted([d["mention_rate"] for d in drift])
        assert rates == [0.0, 100.0]

    def test_get_variation_drift_empty(self, temp_db):
        drift = temp_db.get_variation_drift("nonexistent", "Nike", days=30)
        assert drift == []

    def test_get_all_records_no_filter(self, temp_db):
        run_id = temp_db.create_run()
        temp_db.record_query(run_id, "ollama", "m1", "p1", "Nike", {"Nike": 1})
        temp_db.record_query(run_id, "ollama", "m1", "p2", "Adidas", {"Adidas": 1})
        records = temp_db.get_all_records(brand="*", days=30)
        assert len(records) == 2

    def test_get_all_records_brand_filter(self, temp_db):
        run_id = temp_db.create_run()
        temp_db.record_query(run_id, "ollama", "m1", "p1", "Nike", {"Nike": 1})
        temp_db.record_query(run_id, "ollama", "m1", "p2", "Adidas", {"Adidas": 1})
        records = temp_db.get_all_records(brand="Nike", days=30)
        assert len(records) == 1

    def test_get_all_runs(self, temp_db):
        temp_db.create_run(config_hash="h1")
        temp_db.create_run(config_hash="h2")
        runs = temp_db.get_all_runs(days=30)
        assert len(runs) == 2

    def test_get_record_by_id(self, temp_db):
        run_id = temp_db.create_run()
        record_id = temp_db.record_query(
            run_id, "ollama", "m1", "test prompt", "response", {"Nike": 1}
        )
        record = temp_db.get_record_by_id(record_id)
        assert record is not None
        assert record["id"] == record_id
        assert record["prompt"] == "test prompt"

    def test_get_record_by_id_not_found(self, temp_db):
        record = temp_db.get_record_by_id(99999)
        assert record is None

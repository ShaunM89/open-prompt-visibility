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
        db_path = str(tmp_path / 'test.db')
        db = TrackDatabase(db_path=db_path)
        yield db

    def test_init_creates_tables(self, temp_db):
        """Test that tables are created on initialization."""
        conn = temp_db._get_connection()
        cursor = conn.cursor()

        # Check runs table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='runs'"
        )
        assert cursor.fetchone() is not None

        # Check visibility_records table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='visibility_records'"
        )
        assert cursor.fetchone() is not None

        conn.close()

    def test_create_run(self, temp_db):
        """Test creating a run record."""
        run_id = temp_db.create_run(config_hash='test123')

        assert run_id > 0

        runs = temp_db.get_recent_runs(days=30)
        assert len(runs) == 1
        assert runs[0]['config_hash'] == 'test123'

    def test_record_query(self, temp_db):
        """Test recording a query result."""
        run_id = temp_db.create_run()

        record_id = temp_db.record_query(
            run_id=run_id,
            model_provider='ollama',
            model_name='qwen3.5:122b',
            prompt='Test prompt',
            response_text='Test response mentioning Nike',
            mentions={'Nike': 1}
        )

        assert record_id > 0

        records = temp_db.get_by_run(run_id)
        assert len(records) == 1
        assert records[0]['model_name'] == 'qwen3.5:122b'
        assert 'Nike' in records[0]['mentions_json']

    def test_export_to_csv(self, temp_db):
        """Test CSV export."""
        run_id = temp_db.create_run()
        temp_db.record_query(
            run_id=run_id,
            model_provider='ollama',
            model_name='qwen3.5:122b',
            prompt='Test',
            response_text='Response',
            mentions={'Nike': 1}
        )

        output_path = str(temp_db.db_path.parent / 'test_export.csv')
        temp_db.export_to_csv(output_path)

        assert Path(output_path).exists()

    def test_export_to_json(self, temp_db):
        """Test JSON export."""
        run_id = temp_db.create_run()
        temp_db.record_query(
            run_id=run_id,
            model_provider='ollama',
            model_name='qwen3.5:122b',
            prompt='Test',
            response_text='Response',
            mentions={'Nike': 1}
        )

        output_path = str(temp_db.db_path.parent / 'test_export.json')
        temp_db.export_to_json(output_path)

        assert Path(output_path).exists()

        with open(output_path, 'r') as f:
            data = json.load(f)

        assert len(data) == 1
        assert data[0]['mentions_json'] == '{"Nike": 1}'

    def test_get_stats(self, temp_db):
        """Test statistics retrieval."""
        run_id = temp_db.create_run()
        temp_db.record_query(
            run_id=run_id,
            model_provider='ollama',
            model_name='qwen3.5:122b',
            prompt='Test',
            response_text='Response',
            mentions={}
        )

        stats = temp_db.get_stats()

        assert stats['total_runs'] == 1
        assert stats['total_records'] == 1
        assert stats['unique_models'] == 1

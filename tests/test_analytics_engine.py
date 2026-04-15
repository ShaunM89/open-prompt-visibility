"""Tests for AnalyticsEngine methods."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from src.analyzer import AnalyticsEngine


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def engine(mock_db):
    return AnalyticsEngine(mock_db)


class TestGetSummary:
    def test_no_data(self, engine, mock_db):
        mock_db.get_model_statistics.return_value = []
        result = engine.get_summary("Nike", 30)
        assert result["total_mentions"] == 0
        assert result["total_queries"] == 0

    def test_with_data(self, engine, mock_db):
        mock_db.get_model_statistics.return_value = [
            {
                "model_name": "m1",
                "total_runs": 100,
                "total_mentions": 40,
                "mention_rate_pct": 40.0,
            }
        ]
        result = engine.get_summary("Nike", 30)
        assert result["total_mentions"] == 40
        assert result["total_queries"] == 100
        assert result["overall_mention_rate"] == 40.0


class TestGetVisibilityScore:
    def test_no_data(self, engine, mock_db):
        mock_db.get_trends.return_value = []
        result = engine.get_visibility_score("Nike", 30)
        assert result["score"] == 0.0
        assert result["total_prompts"] == 0

    def test_with_data(self, engine, mock_db):
        mock_db.get_trends.return_value = [
            {"model_name": "m1", "total_queries": 50, "mention_count": 20}
        ]
        mock_db.get_model_statistics.return_value = [
            {
                "model_name": "m1",
                "model_provider": "ollama",
                "total_runs": 50,
                "total_mentions": 20,
                "mention_rate_pct": 40.0,
            }
        ]
        result = engine.get_visibility_score("Nike", 30)
        assert result["score"] == 40.0
        assert result["total_prompts"] == 50
        assert result["successful_prompts"] == 20
        assert len(result["by_model"]) == 1


class TestCompareModels:
    def test_delegates_to_db(self, engine, mock_db):
        mock_db.get_model_statistics.return_value = [{"model_name": "m1"}]
        result = engine.compare_models("Nike", 30)
        assert len(result) == 1
        mock_db.get_model_statistics.assert_called_once_with("Nike", 30)


class TestGetAllMentions:
    def test_delegates_to_db(self, engine, mock_db):
        mock_db.get_all_mentions.return_value = [{"id": 1}]
        result = engine.get_all_mentions(30)
        assert len(result) == 1
        mock_db.get_all_mentions.assert_called_once_with(30)


class TestGetTrends:
    def test_delegates_to_db(self, engine, mock_db):
        mock_db.get_trends.return_value = [{"date": "2024-01-01"}]
        result = engine.get_trends("Nike", 30)
        assert len(result) == 1
        mock_db.get_trends.assert_called_once_with("Nike", 30)


class TestCalculateVariance:
    def test_no_data(self, engine, mock_db):
        mock_db.get_model_statistics.return_value = []
        result = engine.calculate_variance("Nike", 30)
        assert result == {}

    def test_with_data(self, engine, mock_db):
        mock_db.get_model_statistics.return_value = [
            {
                "model_name": "m1",
                "total_runs": 100,
                "total_mentions": 40,
                "mention_rate_pct": 40.0,
            }
        ]
        result = engine.calculate_variance("Nike", 30, 95)
        assert "m1" in result
        assert result["m1"]["mention_rate"] == 40.0
        assert result["m1"]["total_runs"] == 100
        assert result["m1"]["confidence_interval_95"] is not None


class TestGetRunHistory:
    def test_no_runs(self, engine, mock_db):
        mock_db.get_recent_runs.return_value = []
        result = engine.get_run_history(30)
        assert result == []

    def test_with_runs(self, engine, mock_db):
        now = datetime.now(timezone.utc)
        mock_db.get_recent_runs.return_value = [
            {
                "id": 1,
                "started_at": now,
                "completed_at": now + timedelta(minutes=5),
            }
        ]
        mock_db.get_by_run.return_value = [
            {"mentions_json": '{"Nike": 1}', "model_name": "m1"},
            {"mentions_json": "{}", "model_name": "m1"},
        ]
        result = engine.get_run_history(30)
        assert len(result) == 1
        assert result[0]["total_queries"] == 2
        assert result[0]["successful_queries"] == 1


class TestGetRunComparison:
    def test_no_runs(self, engine, mock_db):
        mock_db.get_recent_runs.return_value = []
        result = engine.get_run_comparison("Nike", 30)
        assert result["runs_analyzed"] == 0

    def test_with_runs(self, engine, mock_db):
        now = datetime.now(timezone.utc)
        engine.get_run_history = MagicMock(
            return_value=[
                {
                    "run_id": 1,
                    "started_at": now,
                    "completed_at": now + timedelta(minutes=5),
                    "total_queries": 10,
                }
            ]
        )
        mock_db.get_by_run.return_value = [
            {"mentions_json": '{"Nike": 1}'},
            {"mentions_json": "{}"},
        ]
        result = engine.get_run_comparison("Nike", 30)
        assert result["runs_analyzed"] == 1
        assert len(result["run_trends"]) == 1


class TestGetStatisticalSummary:
    def test_no_runs(self, engine, mock_db):
        engine.get_run_history = MagicMock(return_value=[])
        result = engine.get_statistical_summary("Nike", 30)
        assert result["n_runs"] == 0

    def test_with_runs(self, engine, mock_db):
        engine.get_run_history = MagicMock(
            return_value=[
                {"run_id": 1, "total_queries": 10},
                {"run_id": 2, "total_queries": 10},
            ]
        )
        mock_db.get_by_run.side_effect = [
            [{"mentions_json": '{"Nike": 1}'} for _ in range(4)]
            + [{"mentions_json": "{}"} for _ in range(6)],
            [{"mentions_json": '{"Nike": 1}'} for _ in range(5)]
            + [{"mentions_json": "{}"} for _ in range(5)],
        ]
        result = engine.get_statistical_summary("Nike", 30)
        assert result["n_runs"] == 2
        assert "mean_mention_rate" in result
        assert "std_deviation" in result


class TestHighlightMentions:
    def test_with_mentions(self, engine):
        text = "Nike makes great shoes and Adidas is okay"
        mentions = {"Nike": 1}
        brands = {
            "Nike": {"keywords": ["Nike"], "is_target": True},
            "Adidas": {"keywords": ["Adidas"], "is_target": False},
        }
        result = engine._highlight_mentions(text, mentions, "Nike", brands)
        assert "<mark" in result
        assert "Nike" in result

    def test_empty_text(self, engine):
        result = engine._highlight_mentions("", {}, None, {})
        assert result == ""


class TestInterpretStatistics:
    def test_very_stable(self, engine):
        result = engine._interpret_statistics(cv=5.0, n=10, std_dev=2.0)
        assert "Very stable" in result

    def test_moderate_variation(self, engine):
        result = engine._interpret_statistics(cv=25.0, n=10, std_dev=5.0)
        assert "Moderate variation" in result

    def test_high_variation(self, engine):
        result = engine._interpret_statistics(cv=50.0, n=10, std_dev=10.0)
        assert "High variation" in result

    def test_limited_data(self, engine):
        result = engine._interpret_statistics(cv=5.0, n=3, std_dev=1.0)
        assert "Limited data" in result

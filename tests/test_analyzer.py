"""Tests for mention detection and analytics engine."""

import math
import pytest

from src.analyzer import MentionDetector, AnalyticsEngine
from src.storage import TrackDatabase


class TestMentionDetector:
    """Test keyword-based mention detection."""

    @pytest.fixture
    def mock_config(self):
        return {
            "brands": [
                {
                    "name": "Nike",
                    "keywords": ["Nike", "NIKE", "Just Do It", "Swoosh"],
                    "competitors": [
                        {"name": "Adidas", "keywords": ["Adidas", "ADI"]},
                        {"name": "Reebok", "keywords": ["Reebok"]},
                    ],
                }
            ],
            "tracking": {"detection_method": "keyword"},
        }

    def test_single_brand_mention(self, mock_config):
        detector = MentionDetector(mock_config)
        response = "I prefer Nike for running shoes."
        mentions = detector.detect(response)
        assert "Nike" in mentions
        assert mentions["Nike"] >= 1

    def test_multiple_brand_mentions(self, mock_config):
        detector = MentionDetector(mock_config)
        response = "Nike vs Adidas: both are great brands."
        mentions = detector.detect(response)
        assert "Nike" in mentions
        assert "Adidas" in mentions

    def test_no_mentions(self, mock_config):
        detector = MentionDetector(mock_config)
        response = "The weather is nice today."
        mentions = detector.detect(response)
        assert mentions == {}

    def test_case_insensitive(self, mock_config):
        detector = MentionDetector(mock_config)
        response = "I bought NIKE shoes yesterday."
        mentions = detector.detect(response)
        assert "Nike" in mentions

    def test_slogan_detection(self, mock_config):
        detector = MentionDetector(mock_config)
        response = "Just Do It - the best slogan ever."
        mentions = detector.detect(response)
        assert "Nike" in mentions


class TestAnalyticsEngineConfidenceInterval:
    """Test confidence interval calculations."""

    @pytest.fixture
    def engine(self, tmp_path):
        db = TrackDatabase(db_path=str(tmp_path / "test.db"))
        return AnalyticsEngine(db)

    def test_ci_returns_none_for_zero_samples(self, engine):
        result = engine._calculate_confidence_interval(50, 0, 95)
        assert result is None

    def test_ci_returns_none_for_zero_proportion(self, engine):
        result = engine._calculate_confidence_interval(0, 100, 95)
        assert result is None

    def test_ci_returns_tuple_for_valid_input(self, engine):
        result = engine._calculate_confidence_interval(75, 100, 95)
        assert result is not None
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_ci_lower_less_than_upper(self, engine):
        result = engine._calculate_confidence_interval(75, 100, 95)
        assert result[0] < result[1]

    def test_ci_contains_proportion(self, engine):
        proportion = 75
        result = engine._calculate_confidence_interval(proportion, 100, 95)
        assert result[0] <= proportion
        assert result[1] >= proportion

    def test_ci_narrows_with_larger_sample(self, engine):
        ci_small = engine._calculate_confidence_interval(75, 30, 95)
        ci_large = engine._calculate_confidence_interval(75, 1000, 95)
        width_small = ci_small[1] - ci_small[0]
        width_large = ci_large[1] - ci_large[0]
        assert width_large < width_small

    def test_ci_bounds_between_0_and_100(self, engine):
        result = engine._calculate_confidence_interval(99, 10, 95)
        assert result[0] >= 0
        assert result[1] <= 100

    def test_ci_99_wider_than_95(self, engine):
        ci_95 = engine._calculate_confidence_interval(50, 100, 95)
        ci_99 = engine._calculate_confidence_interval(50, 100, 99)
        width_95 = ci_95[1] - ci_95[0]
        width_99 = ci_99[1] - ci_99[0]
        assert width_99 > width_95


class TestAnalyticsEngineSignificance:
    """Test significance assessment."""

    @pytest.fixture
    def engine(self, tmp_path):
        db = TrackDatabase(db_path=str(tmp_path / "test.db"))
        return AnalyticsEngine(db)

    def test_insufficient_data_for_small_samples(self, engine):
        result = engine._assess_significance(75, 5, 20)
        assert result == "Insufficient data"

    def test_insufficient_data_for_zero_error(self, engine):
        result = engine._assess_significance(75, 0, 50)
        assert result == "Insufficient data"

    def test_zero_rate_returns_noise(self, engine):
        result = engine._assess_significance(0, 5, 50)
        assert "noise" in result.lower()

    def test_high_rate_returns_significant(self, engine):
        result = engine._assess_significance(80, 5, 100)
        assert "distinguishable" in result.lower() or "signal" in result.lower()


class TestAnalyticsEngineStatisticalSummary:
    """Test statistical summary calculations."""

    @pytest.fixture
    def populated_engine(self, tmp_path):
        db = TrackDatabase(db_path=str(tmp_path / "test.db"))
        for run_idx in range(5):
            run_id = db.create_run(config_hash=f"test_{run_idx}")
            for i in range(10):
                mentions = {"Nike": 1} if i < 8 else {}
                db.record_query(
                    run_id=run_id,
                    model_provider="ollama",
                    model_name="qwen3.5",
                    prompt=f"Test prompt {i}",
                    response_text=f"Response mentioning Nike {i}" if i < 8 else "No brand",
                    mentions=mentions,
                )
        return AnalyticsEngine(db)

    def test_summary_has_required_fields(self, populated_engine):
        result = populated_engine.calculate_statistical_summary("Nike", days=30)
        assert "brand" in result
        assert "period_days" in result
        assert "model_stats" in result

    def test_summary_returns_model_data(self, populated_engine):
        result = populated_engine.calculate_statistical_summary("Nike", days=30)
        assert len(result["model_stats"]) > 0
        ms = result["model_stats"][0]
        assert "model_name" in ms
        assert "mention_rate" in ms
        assert "confidence_interval_lower" in ms

    def test_variance_calculation(self, tmp_path):
        db = TrackDatabase(db_path=str(tmp_path / "test.db"))
        engine = AnalyticsEngine(db)
        assert engine.calculate_variance("Nike") == {}


class TestAnalyticsEngineInterpretation:
    """Test interpretation helpers."""

    @pytest.fixture
    def engine(self, tmp_path):
        db = TrackDatabase(db_path=str(tmp_path / "test.db"))
        return AnalyticsEngine(db)

    def test_interpret_aggregate_stats_low_rate(self, engine):
        result = engine._interpret_aggregate_stats(20, 10)
        assert "Low" in result

    def test_interpret_aggregate_stats_high_rate(self, engine):
        result = engine._interpret_aggregate_stats(80, 100)
        assert "Strong" in result

    def test_interpret_statistics_stable(self, engine):
        result = engine._interpret_statistics(5, 10, 2)
        assert "stable" in result.lower()

    def test_interpret_statistics_high_variation(self, engine):
        result = engine._interpret_statistics(50, 10, 20)
        assert "high variation" in result.lower()

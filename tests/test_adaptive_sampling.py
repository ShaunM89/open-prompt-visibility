"""Tests for adaptive sampling: RunningStats, AdaptiveSampler, convergence logic."""

import pytest

from src.analyzer import (
    CIStrategy,
    WilsonCIStrategy,
    RunningStats,
    AdaptiveSampler,
)


class TestWilsonCIStrategy:
    def _make_stats(self, scores: list[float]) -> RunningStats:
        rs = RunningStats(WilsonCIStrategy())
        for s in scores:
            rs.record(s)
        return rs

    def test_ci_none_for_empty(self):
        rs = self._make_stats([])
        assert rs.ci is None

    def test_ci_valid_for_all_zeros(self):
        rs = self._make_stats([0, 0, 0, 0, 0])
        assert rs.ci is not None
        assert rs.ci[0] == 0.0
        assert rs.ci[1] > 0.0

    def test_ci_returns_tuple_for_mixed(self):
        rs = self._make_stats([1, 1, 0, 1, 0])
        assert rs.ci is not None
        assert len(rs.ci) == 2
        assert rs.ci[0] < rs.ci[1]

    def test_ci_width_for_50_percent(self):
        rs = self._make_stats([1, 0] * 50)
        assert rs.ci_width is not None
        assert rs.ci_width > 0

    def test_ci_width_narrows_with_more_data(self):
        rs_small = self._make_stats([1, 0, 1, 0, 1, 0, 1, 0, 1, 0])
        rs_large = self._make_stats([1, 0] * 100)
        assert rs_large.ci_width < rs_small.ci_width


class TestRunningStats:
    @pytest.fixture
    def stats(self):
        return RunningStats(WilsonCIStrategy(), confidence_level=95.0)

    def test_initial_state(self, stats):
        assert stats.n == 0
        assert stats.mean_score == 0.0
        assert stats.ci is None
        assert stats.ci_width is None

    def test_record_increments_n(self, stats):
        stats.record(1.0)
        stats.record(0.0)
        assert stats.n == 2

    def test_mean_score_binary(self, stats):
        for _ in range(7):
            stats.record(1.0)
        for _ in range(3):
            stats.record(0.0)
        assert stats.mean_score == pytest.approx(70.0, abs=0.1)

    def test_mean_score_single(self, stats):
        stats.record(1.0)
        assert stats.mean_score == 100.0

    def test_se_positive_for_mixed(self, stats):
        for _ in range(10):
            stats.record(1.0)
        for _ in range(10):
            stats.record(0.0)
        assert stats.se > 0

    def test_converged_false_below_min(self, stats):
        for _ in range(5):
            stats.record(1.0)
        assert stats.converged(target_width=20.0, min_queries=10) is False

    def test_converged_true_when_narrow(self, stats):
        for _ in range(80):
            stats.record(1.0)
        for _ in range(20):
            stats.record(0.0)
        assert stats.converged(target_width=20.0, min_queries=10) is True

    def test_converged_false_when_wide(self, stats):
        for _ in range(6):
            stats.record(1.0)
        for _ in range(4):
            stats.record(0.0)
        assert stats.converged(target_width=5.0, min_queries=5) is False

    def test_estimate_queries_to_converge(self, stats):
        for _ in range(6):
            stats.record(1.0)
        for _ in range(4):
            stats.record(0.0)
        est = stats.estimate_queries_to_converge(5.0)
        assert est is not None
        assert est > stats.n

    def test_estimate_none_for_insufficient_data(self, stats):
        stats.record(1.0)
        assert stats.estimate_queries_to_converge(10.0) is None

    def test_ci_width_property(self, stats):
        for _ in range(10):
            stats.record(1.0)
        for _ in range(10):
            stats.record(0.0)
        assert stats.ci_width is not None
        assert stats.ci_width > 0


class TestAdaptiveSampler:
    @pytest.fixture
    def sampler(self):
        config = {
            "tracking": {
                "queries_per_prompt": 10,
                "adaptive_sampling": {
                    "enabled": True,
                    "target_ci_width": 20.0,
                    "max_queries": 200,
                    "check_interval": 5,
                    "convergence_scope": "primary_brand",
                },
                "statistical_analysis": {"confidence_level": 95},
            }
        }
        return AdaptiveSampler(config)

    def test_record_creates_stats(self, sampler):
        sampler.record("model_a", "prompt_1", "Nike", 1.0)
        stats = sampler.get_stats("model_a", "prompt_1", "Nike")
        assert stats is not None
        assert stats.n == 1

    def test_should_stop_false_below_min(self, sampler):
        for i in range(5):
            sampler.record("model_a", "prompt_1", "Nike", 1.0)
        assert sampler.should_stop("model_a", "prompt_1", "Nike") is False

    def test_should_stop_true_when_converged(self, sampler):
        for _ in range(80):
            sampler.record("model_a", "prompt_1", "Nike", 1.0)
        for _ in range(20):
            sampler.record("model_a", "prompt_1", "Nike", 0.0)
        assert sampler.should_stop("model_a", "prompt_1", "Nike") is True

    def test_should_stop_primary_brand_scope(self, sampler):
        for _ in range(80):
            sampler.record("m", "p", "Nike", 1.0)
            sampler.record("m", "p", "Adidas", 0.0)
        for _ in range(20):
            sampler.record("m", "p", "Nike", 0.0)
            sampler.record("m", "p", "Adidas", 1.0)
        assert sampler.should_stop("m", "p", "Nike", ["Nike", "Adidas"]) is True

    def test_should_stop_all_brands_scope(self):
        config = {
            "tracking": {
                "queries_per_prompt": 10,
                "adaptive_sampling": {
                    "target_ci_width": 5.0,
                    "max_queries": 500,
                    "check_interval": 5,
                    "convergence_scope": "all_tracked_brands",
                },
                "statistical_analysis": {"confidence_level": 95},
            }
        }
        sampler = AdaptiveSampler(config)
        for _ in range(80):
            sampler.record("m", "p", "Nike", 1.0)
            sampler.record("m", "p", "Adidas", 0.0)
        for _ in range(20):
            sampler.record("m", "p", "Nike", 0.0)
            sampler.record("m", "p", "Adidas", 1.0)
        assert sampler.should_stop("m", "p", "Nike", ["Nike", "Adidas"]) is False

    def test_max_queries_ceiling(self, sampler):
        for _ in range(200):
            sampler.record("m", "p", "Nike", 1.0)
        stats = sampler.get_stats("m", "p", "Nike")
        assert stats.n == 200

    def test_estimate_remaining(self, sampler):
        for _ in range(6):
            sampler.record("m", "p", "Nike", 1.0)
        for _ in range(4):
            sampler.record("m", "p", "Nike", 0.0)
        est = sampler.estimate_remaining("m", "p", "Nike")
        assert est is not None
        assert est <= sampler.max_queries

    def test_get_status(self, sampler):
        for _ in range(15):
            sampler.record("m", "p", "Nike", 1.0)
            sampler.record("m", "p", "Adidas", 0.0)
        status = sampler.get_status("Nike", ["Nike", "Adidas"])
        assert "pairs" in status
        assert "summary" in status
        assert status["adaptive_enabled"] is True
        assert status["summary"]["total_pairs"] == 1

    def test_independent_models(self, sampler):
        for _ in range(80):
            sampler.record("model_a", "p", "Nike", 1.0)
        for _ in range(20):
            sampler.record("model_a", "p", "Nike", 0.0)
        for _ in range(5):
            sampler.record("model_b", "p", "Nike", 1.0)
        assert sampler.should_stop("model_a", "p", "Nike") is True
        assert sampler.should_stop("model_b", "p", "Nike") is False

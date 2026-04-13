"""Tests for AdaptiveSampler state reconstruction and ETA estimation."""

import pytest

from src.analyzer import (
    AdaptiveSampler,
    RunningStats,
    WilsonCIStrategy,
)


def _make_config(adaptive_enabled=True, max_queries=200, target_ci_width=20.0):
    return {
        "tracking": {
            "queries_per_prompt": 10,
            "adaptive_sampling": {
                "enabled": adaptive_enabled,
                "max_queries": max_queries,
                "target_ci_width": target_ci_width,
                "check_interval": 5,
                "convergence_scope": "primary_brand",
            },
            "statistical_analysis": {"confidence_level": 95},
        }
    }


def _make_records(data):
    """Build fake visibility_records for restore_from_records.

    data: list of (model_name, prompt, mentions_dict)
    """
    return [
        {"model_name": m, "prompt": p, "mentions_json": json.dumps(mentions)}
        for m, p, mentions in data
    ]


import json


class TestSamplerRestoreFromRecords:
    """Test reconstructing AdaptiveSampler from DB records."""

    def test_restore_empty_records(self):
        sampler = AdaptiveSampler(_make_config())
        sampler.restore_from_records([], ["Nike", "Adidas"])
        assert len(sampler._stats) == 0

    def test_restore_single_brand_mentioned(self):
        sampler = AdaptiveSampler(_make_config())
        records = _make_records(
            [
                ("model_a", "prompt1", {"Nike": 1}),
                ("model_a", "prompt1", {}),
                ("model_a", "prompt1", {"Nike": 1}),
            ]
        )
        sampler.restore_from_records(records, ["Nike"])

        stats = sampler.get_stats("model_a", "prompt1", "Nike")
        assert stats is not None
        assert stats.n == 3
        assert stats.mean_score == pytest.approx(200.0 / 3.0, rel=0.01)

    def test_restore_multiple_brands(self):
        sampler = AdaptiveSampler(_make_config())
        records = _make_records(
            [
                ("model_a", "prompt1", {"Nike": 1}),
                ("model_a", "prompt1", {"Adidas": 1}),
                ("model_a", "prompt1", {}),
            ]
        )
        sampler.restore_from_records(records, ["Nike", "Adidas"])

        nike = sampler.get_stats("model_a", "prompt1", "Nike")
        adidas = sampler.get_stats("model_a", "prompt1", "Adidas")
        assert nike.n == 3
        assert adidas.n == 3

    def test_restore_multiple_models_and_prompts(self):
        sampler = AdaptiveSampler(_make_config())
        records = _make_records(
            [
                ("model_a", "prompt1", {"Nike": 1}),
                ("model_b", "prompt1", {}),
                ("model_a", "prompt2", {"Nike": 1}),
                ("model_b", "prompt2", {"Nike": 1}),
            ]
        )
        sampler.restore_from_records(records, ["Nike"])

        assert sampler.get_stats("model_a", "prompt1", "Nike").n == 1
        assert sampler.get_stats("model_b", "prompt1", "Nike").n == 1
        assert sampler.get_stats("model_a", "prompt2", "Nike").n == 1
        assert sampler.get_stats("model_b", "prompt2", "Nike").n == 1

    def test_restore_handles_empty_mentions_json(self):
        sampler = AdaptiveSampler(_make_config())
        records = _make_records(
            [
                ("model_a", "prompt1", {}),
            ]
        )
        sampler.restore_from_records(records, ["Nike"])
        stats = sampler.get_stats("model_a", "prompt1", "Nike")
        assert stats.n == 1
        assert stats.mean_score == 0.0

    def test_restore_handles_null_mentions(self):
        sampler = AdaptiveSampler(_make_config())
        records = [{"model_name": "model_a", "prompt": "p1", "mentions_json": None}]
        sampler.restore_from_records(records, ["Nike"])
        stats = sampler.get_stats("model_a", "p1", "Nike")
        assert stats.n == 1

    def test_restore_preserves_convergence_check(self):
        sampler = AdaptiveSampler(_make_config(max_queries=200, target_ci_width=20.0))
        records = _make_records(
            [
                ("model_a", "prompt1", {"Nike": 1}),
            ]
            * 90
        )
        sampler.restore_from_records(records, ["Nike"])

        assert sampler.should_stop("model_a", "prompt1", "Nike")


class TestGetConvergedPairs:
    """Test get_converged_pairs method."""

    def test_nothing_converged(self):
        sampler = AdaptiveSampler(_make_config())
        sampler.record("model_a", "prompt1", "Nike", 1.0)
        sampler.record("model_a", "prompt1", "Nike", 0.0)

        converged = sampler.get_converged_pairs("Nike")
        assert converged == set()

    def test_one_pair_converged(self):
        sampler = AdaptiveSampler(_make_config())
        for _ in range(90):
            sampler.record("model_a", "prompt1", "Nike", 1.0)

        converged = sampler.get_converged_pairs("Nike")
        assert ("model_a", "prompt1") in converged

    def test_mixed_convergence(self):
        sampler = AdaptiveSampler(_make_config())
        for _ in range(90):
            sampler.record("model_a", "prompt1", "Nike", 1.0)
        for _ in range(5):
            sampler.record("model_a", "prompt2", "Nike", 1.0)
        for _ in range(60):
            sampler.record("model_b", "prompt1", "Nike", 1.0)
        for _ in range(60):
            sampler.record("model_b", "prompt1", "Nike", 0.0)

        converged = sampler.get_converged_pairs("Nike")
        assert ("model_a", "prompt1") in converged
        assert ("model_a", "prompt2") not in converged
        assert ("model_b", "prompt1") in converged

    def test_all_brands_scope(self):
        config = _make_config()
        config["tracking"]["adaptive_sampling"]["convergence_scope"] = "all_tracked_brands"
        sampler = AdaptiveSampler(config)

        for _ in range(90):
            sampler.record("model_a", "prompt1", "Nike", 1.0)
        # Adidas not converged
        sampler.record("model_a", "prompt1", "Adidas", 0.0)

        converged = sampler.get_converged_pairs("Nike", ["Nike", "Adidas"])
        assert ("model_a", "prompt1") not in converged


class TestEstimateTotalQueries:
    """Test ETA/progress estimation."""

    def test_estimate_with_no_data(self):
        sampler = AdaptiveSampler(_make_config())
        result = sampler.estimate_total_queries(
            total_prompts=10, enabled_models=["ollama:gemma4:e2b"], primary_brand="Nike"
        )
        assert result["total_pairs"] == 10
        assert result["completed_queries"] == 0
        assert result["completion_pct"] == 0.0

    def test_estimate_with_partial_data(self):
        sampler = AdaptiveSampler(_make_config())
        for _ in range(50):
            sampler.record("gemma4:e2b", "prompt1", "Nike", 1.0)
        for _ in range(50):
            sampler.record("gemma4:e2b", "prompt2", "Nike", 1.0)

        result = sampler.estimate_total_queries(
            total_prompts=10, enabled_models=["ollama:gemma4:e2b"], primary_brand="Nike"
        )
        assert result["total_pairs"] == 10
        assert result["completed_queries"] == 100
        assert result["converged_pairs"] == 2
        assert result["completion_pct"] > 0

    def test_estimate_all_converged(self):
        sampler = AdaptiveSampler(_make_config())
        for p in range(3):
            for _ in range(90):
                sampler.record("gemma4:e2b", f"prompt{p}", "Nike", 1.0)

        result = sampler.estimate_total_queries(
            total_prompts=3, enabled_models=["ollama:gemma4:e2b"], primary_brand="Nike"
        )
        assert result["converged_pairs"] == 3
        assert result["total_pairs"] == 3

    def test_estimate_increases_monotonically_with_data(self):
        sampler = AdaptiveSampler(_make_config())
        prompts = [f"prompt{i}" for i in range(5)]

        pct_no_data = sampler.estimate_total_queries(
            total_prompts=5, enabled_models=["ollama:gemma4:e2b"], primary_brand="Nike"
        )["completion_pct"]

        for _ in range(50):
            sampler.record("gemma4:e2b", prompts[0], "Nike", 1.0)

        pct_with_data = sampler.estimate_total_queries(
            total_prompts=5, enabled_models=["ollama:gemma4:e2b"], primary_brand="Nike"
        )["completion_pct"]

        assert pct_with_data > pct_no_data

"""Tests for LLM cost estimation."""

import pytest

from src.cost import (
    DEFAULT_PRICING,
    ModelCost,
    estimate_run_cost,
)


class TestEstimateRunCost:
    def test_local_only_models_zero_cost(self):
        models = [{"provider": "ollama", "model": "gemma4:e2b"}]
        result = estimate_run_cost(models, num_prompts=100, max_queries_per_prompt=200)
        assert result["total_max_cost"] == 0.0
        assert result["total_expected_cost"] == 0.0
        assert result["is_local"] is True

    def test_single_cloud_model(self):
        models = [{"provider": "openai", "model": "gpt-4o-mini"}]
        result = estimate_run_cost(models, num_prompts=100, max_queries_per_prompt=200)
        assert result["total_max_cost"] > 0
        assert result["total_expected_cost"] > 0
        assert result["total_expected_cost"] < result["total_max_cost"]
        assert result["is_local"] is False

    def test_adaptive_reduction_halves_cost(self):
        models = [{"provider": "openai", "model": "gpt-4o-mini"}]
        max_cost = estimate_run_cost(models, 100, 200, adaptive_reduction=1.0)
        half_cost = estimate_run_cost(models, 100, 200, adaptive_reduction=0.5)
        assert half_cost["total_expected_cost"] == pytest.approx(
            max_cost["total_expected_cost"] / 2, rel=0.01
        )

    def test_multiple_models(self):
        models = [
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "anthropic", "model": "claude-3.5-haiku"},
        ]
        result = estimate_run_cost(models, num_prompts=50, max_queries_per_prompt=200)
        assert len(result["models"]) == 2
        assert result["total_max_cost"] > 0

    def test_mixed_local_and_cloud(self):
        models = [
            {"provider": "ollama", "model": "gemma4:e2b"},
            {"provider": "openai", "model": "gpt-4o-mini"},
        ]
        result = estimate_run_cost(models, num_prompts=100, max_queries_per_prompt=200)
        assert result["is_local"] is False
        assert result["models"][0].total_cost == 0.0
        assert result["models"][1].total_cost > 0.0

    def test_unknown_cloud_model_zero_cost(self):
        models = [{"provider": "custom", "model": "my-model"}]
        result = estimate_run_cost(models, num_prompts=100, max_queries_per_prompt=200)
        assert result["total_max_cost"] == 0.0
        assert result["is_local"] is True

    def test_user_pricing_override(self):
        user_pricing = {
            "custom": {
                "my-model": {"input_per_million": 1.0, "output_per_million": 2.0},
            }
        }
        models = [{"provider": "custom", "model": "my-model"}]
        result = estimate_run_cost(
            models, 100, 200, user_pricing=user_pricing, adaptive_reduction=1.0
        )
        assert result["total_max_cost"] > 0
        assert result["is_local"] is False

    def test_custom_token_estimates(self):
        models = [{"provider": "openai", "model": "gpt-4o-mini"}]
        low = estimate_run_cost(
            models,
            100,
            200,
            adaptive_reduction=1.0,
            estimated_input_tokens=50,
            estimated_output_tokens=200,
        )
        high = estimate_run_cost(
            models,
            100,
            200,
            adaptive_reduction=1.0,
            estimated_input_tokens=200,
            estimated_output_tokens=800,
        )
        assert high["total_max_cost"] > low["total_max_cost"]

    def test_query_counts(self):
        models = [{"provider": "openai", "model": "gpt-4o-mini"}]
        result = estimate_run_cost(models, num_prompts=10, max_queries_per_prompt=100)
        assert result["max_queries"] == 1000
        assert result["estimated_queries"] == 500


class TestModelCost:
    def test_total_cost(self):
        mc = ModelCost("openai", "gpt-4o", 100, 10000, 40000, 0.5, 2.0)
        assert mc.total_cost == 2.5

    def test_zero_cost(self):
        mc = ModelCost("ollama", "local", 100, 10000, 40000, 0.0, 0.0)
        assert mc.total_cost == 0.0

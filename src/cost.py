"""LLM cost estimation for tracking runs."""

from dataclasses import dataclass
from typing import Dict, Optional


DEFAULT_PRICING: Dict[str, Dict[str, Dict[str, float]]] = {
    "openai": {
        "gpt-4o-mini": {"input_per_million": 0.15, "output_per_million": 0.60},
        "gpt-4o": {"input_per_million": 2.50, "output_per_million": 10.00},
        "gpt-4.1-mini": {"input_per_million": 0.40, "output_per_million": 1.60},
        "gpt-4.1": {"input_per_million": 2.00, "output_per_million": 8.00},
    },
    "anthropic": {
        "claude-3.5-haiku": {"input_per_million": 0.80, "output_per_million": 4.00},
        "claude-3.5-sonnet": {"input_per_million": 3.00, "output_per_million": 15.00},
        "claude-4-sonnet": {"input_per_million": 3.00, "output_per_million": 15.00},
    },
    "ollama": {},
}

ESTIMATED_INPUT_TOKENS = 100
ESTIMATED_OUTPUT_TOKENS = 400


@dataclass
class ModelCost:
    provider: str
    model: str
    queries: int
    input_tokens: int
    output_tokens: int
    input_cost: float
    output_cost: float

    @property
    def total_cost(self) -> float:
        return self.input_cost + self.output_cost


def _get_pricing(provider: str, model: str, user_pricing: Optional[dict] = None) -> Optional[dict]:
    if user_pricing:
        provider_prices = user_pricing.get(provider, {})
        if model in provider_prices:
            return provider_prices[model]

    provider_prices = DEFAULT_PRICING.get(provider, {})
    if model in provider_prices:
        return provider_prices[model]
    return None


def estimate_run_cost(
    models: list,
    num_prompts: int,
    max_queries_per_prompt: int,
    adaptive_reduction: float = 0.5,
    user_pricing: Optional[dict] = None,
    estimated_input_tokens: int = ESTIMATED_INPUT_TOKENS,
    estimated_output_tokens: int = ESTIMATED_OUTPUT_TOKENS,
) -> Dict[str, object]:
    """Estimate cost for a tracking run.

    Args:
        models: List of model config dicts with 'provider' and 'model' keys
        num_prompts: Total number of prompts to run
        max_queries_per_prompt: Max queries per prompt (adaptive ceiling)
        adaptive_reduction: Expected fraction of max queries (default 0.5 = 50%)
        user_pricing: Optional user pricing overrides
        estimated_input_tokens: Estimated input tokens per query
        estimated_output_tokens: Estimated output tokens per query

    Returns:
        Dict with 'models', 'total_cost', 'expected_cost', 'is_local'
    """
    estimated_queries = int(num_prompts * max_queries_per_prompt * adaptive_reduction)
    max_queries = num_prompts * max_queries_per_prompt

    model_costs = []
    total_max_cost = 0.0
    total_expected_cost = 0.0
    is_local = True

    for model_cfg in models:
        provider = model_cfg.get("provider", "")
        model = model_cfg.get("model", "")
        pricing = _get_pricing(provider, model, user_pricing)

        if provider == "ollama" or pricing is None:
            model_costs.append(
                ModelCost(
                    provider=provider,
                    model=model,
                    queries=max_queries,
                    input_tokens=max_queries * estimated_input_tokens,
                    output_tokens=max_queries * estimated_output_tokens,
                    input_cost=0.0,
                    output_cost=0.0,
                )
            )
            continue

        is_local = False
        in_price = pricing.get("input_per_million", 0.0)
        out_price = pricing.get("output_per_million", 0.0)

        max_in_tokens = max_queries * estimated_input_tokens
        max_out_tokens = max_queries * estimated_output_tokens
        max_cost = (max_in_tokens / 1_000_000 * in_price) + (max_out_tokens / 1_000_000 * out_price)

        exp_in_tokens = estimated_queries * estimated_input_tokens
        exp_out_tokens = estimated_queries * estimated_output_tokens
        exp_cost = (exp_in_tokens / 1_000_000 * in_price) + (exp_out_tokens / 1_000_000 * out_price)

        total_max_cost += max_cost
        total_expected_cost += exp_cost

        model_costs.append(
            ModelCost(
                provider=provider,
                model=model,
                queries=max_queries,
                input_tokens=max_in_tokens,
                output_tokens=max_out_tokens,
                input_cost=max_cost * (in_price / (in_price + out_price))
                if (in_price + out_price) > 0
                else 0.0,
                output_cost=max_cost * (out_price / (in_price + out_price))
                if (in_price + out_price) > 0
                else 0.0,
            )
        )

    return {
        "models": model_costs,
        "total_max_cost": round(total_max_cost, 4),
        "total_expected_cost": round(total_expected_cost, 4),
        "estimated_queries": estimated_queries,
        "max_queries": max_queries,
        "is_local": is_local,
    }

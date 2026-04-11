"""Mention detection and analytics engine."""

import json
import math
import re
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models import OllamaAdapter
from .storage import TrackDatabase


class MentionDetector:
    """Hybrid mention detection (keyword + LLM confirmation)."""

    def __init__(self, config: dict):
        self.config = config
        self.brands = self._load_brands(config.get("brands", []))
        self.detection_method = config.get("tracking", {}).get("detection_method", "both")

        # Initialize LLM detector if needed
        # Check if model key exists to initialize LLM adapter
        if self.detection_method in ("llm", "both"):
            llm_config = config.get("tracking", {}).get("llm_detection", {})
            model_name = llm_config.get("model")
            if model_name:
                self.llm_adapter = OllamaAdapter(
                    model=model_name,
                    temperature=llm_config.get("temperature", 0.1),
                )
            else:
                self.llm_adapter = None
        else:
            self.llm_adapter = None

    def _load_brands(self, brands_config: List[dict]) -> Dict[str, dict]:
        """Load brands and their keywords from config."""
        brands = {}
        for brand in brands_config:
            brand_name = brand["name"]
            brands[brand_name] = {
                "keywords": brand.get("keywords", []),
                "competitors": brand.get("competitors", []),
            }

        # Also add competitors as standalone brands
        for brand in brands_config:
            for competitor in brand.get("competitors", []):
                comp_name = competitor["name"]
                if comp_name not in brands:
                    brands[comp_name] = {
                        "keywords": competitor.get("keywords", [comp_name]),
                        "competitors": [],
                    }

        return brands

    def detect(self, response_text: str) -> Dict[str, int]:
        """Detect brand mentions in response text."""
        if self.detection_method == "keyword":
            return self._keyword_detect(response_text)
        elif self.detection_method == "llm":
            return self._llm_detect(response_text)
        else:  # 'both' - keyword first, LLM confirmation
            keyword_mentions = self._keyword_detect(response_text)
            if keyword_mentions:
                return self._llm_confirm(response_text, keyword_mentions)
            return keyword_mentions

    def _keyword_detect(self, response_text: str) -> Dict[str, int]:
        """Simple keyword-based mention detection."""
        mentions: Dict[str, int] = defaultdict(int)
        text_upper = response_text.upper()

        for brand_name, brand_config in self.brands.items():
            for keyword in brand_config["keywords"]:
                # Case-insensitive matching
                count = len(re.findall(re.escape(keyword.upper()), text_upper))
                if count > 0:
                    mentions[brand_name] += count

        return dict(mentions) if mentions else {}

    def _llm_detect(self, response_text: str) -> Dict[str, int]:
        """LLM-based mention detection."""
        if not self.llm_adapter:
            return {}

        prompt = f"""
You are analyzing text for brand mentions. Extract ALL brand mentions from the following response.

Known brands: {list(self.brands.keys())}

Response text:
{response_text}

Return ONLY a JSON object with brand names as keys and mention counts as values.
Example: {{"Nike": 2, "Adidas": 1}}
If no brands are mentioned, return {{}}.
"""

        try:
            result = self.llm_adapter.query(prompt)
            # Clean up the response
            result = result.strip()
            if result.startswith("```json"):
                result = result[7:]
            if result.endswith("```"):
                result = result[:-3]
            result = result.strip()

            return json.loads(result)
        except Exception:
            # Fall back to keyword detection on failure
            return self._keyword_detect(response_text)

    def _llm_confirm(self, response_text: str, keyword_mentions: Dict[str, int]) -> Dict[str, int]:
        """Use LLM to confirm keyword-drafted mentions."""
        if not self.llm_adapter:
            return keyword_mentions

        mentioned_brands = ", ".join(keyword_mentions.keys())
        prompt = f"""
Confirm these brand mentions in the response. Return 1 if the brand is mentioned, 0 if not.

Brands to check: {mentioned_brands}

Response text:
{response_text}

Return ONLY valid JSON:
{{"brand1": 1, "brand2": 0}}
"""

        try:
            result = self.llm_adapter.query(prompt)
            result = result.strip()
            if result.startswith("```json"):
                result = result[7:]
            if result.endswith("```"):
                result = result[:-3]
            result = result.strip()

            confirmed = json.loads(result)

            # Only keep mentions that LLM confirmed (value = 1)
            return {
                brand: count
                for brand, count in keyword_mentions.items()
                if confirmed.get(brand) == 1
            }
        except Exception:
            # LLM failed, return keyword results
            return keyword_mentions


class CIStrategy(ABC):
    """Abstract base class for confidence interval calculation strategies.

    Designed for extensibility: binary mention detection uses WilsonCIStrategy.
    Future sentiment/prominence scoring (issue #3) can add TDistributionCIStrategy,
    BootstrapCIStrategy, etc. without modifying the convergence pipeline.
    """

    @abstractmethod
    def calculate(
        self, n: int, scores: List[float], confidence_level: float = 95.0
    ) -> Optional[Tuple[float, float]]:
        pass


class WilsonCIStrategy(CIStrategy):
    """Wilson score confidence interval for binomial proportions (0/1 scores)."""

    Z_SCORES = {90: 1.645, 95: 1.96, 99: 2.576}

    def calculate(
        self, n: int, scores: List[float], confidence_level: float = 95.0
    ) -> Optional[Tuple[float, float]]:
        if n == 0 or not scores:
            return None
        p = sum(scores) / n
        if p == 0:
            return None
        z = self.Z_SCORES.get(int(confidence_level), 1.96)
        denominator = 1 + z**2 / n
        centre = (p + z**2 / (2 * n)) / denominator
        spread = (z * math.sqrt((p * (1 - p) + z**2 / (4 * n)) / n)) / denominator
        lower = max(0.0, (centre - spread) * 100)
        upper = min(100.0, (centre + spread) * 100)
        return (lower, upper)


class RunningStats:
    """Incremental statistics accumulator for adaptive sampling.

    Accepts float scores (1.0/0.0 for binary, continuous for future sentiment).
    Maintains running mean, CI, and CI width in O(1) per update.
    """

    def __init__(self, ci_strategy: CIStrategy, confidence_level: float = 95.0):
        self.ci_strategy = ci_strategy
        self.confidence_level = confidence_level
        self.n: int = 0
        self._sum: float = 0.0
        self._scores: List[float] = []

    def record(self, score: float) -> None:
        self.n += 1
        self._sum += score
        self._scores.append(score)

    @property
    def mean_score(self) -> float:
        return (self._sum / self.n * 100) if self.n > 0 else 0.0

    @property
    def ci(self) -> Optional[Tuple[float, float]]:
        return self.ci_strategy.calculate(self.n, self._scores, self.confidence_level)

    @property
    def ci_width(self) -> Optional[float]:
        interval = self.ci
        if interval is None:
            return None
        return interval[1] - interval[0]

    @property
    def se(self) -> float:
        if self.n == 0:
            return 0.0
        p = self._sum / self.n
        return math.sqrt(p * (1 - p) / self.n) * 100 if 0 < p < 1 else 0.0

    def converged(self, target_width: float, min_queries: int) -> bool:
        if self.n < min_queries:
            return False
        width = self.ci_width
        return width is not None and width <= target_width

    def estimate_queries_to_converge(self, target_width: float) -> Optional[int]:
        if self.n < 2 or self.ci_width is None or self.ci_width <= 0:
            return None
        ratio = self.ci_width / target_width
        estimated = int(self.n * ratio * ratio)
        return max(estimated, self.n + 1)


@dataclass
class ConvergencePair:
    model: str
    prompt: str
    brand: str
    queries_completed: int = 0
    converged: bool = False
    ci_width: Optional[float] = None
    mean_score: float = 0.0
    ci: Optional[Tuple[float, float]] = None


class AdaptiveSampler:
    """Manages per (model, prompt, brand) convergence tracking.

    Default convergence scope: primary_brand -- stops when the audited brand converges.
    Stricter mode: all_tracked_brands -- waits for every brand keyword.
    """

    def __init__(self, config: dict):
        adaptive_config = config.get("tracking", {}).get("adaptive_sampling", {})
        self.target_ci_width = adaptive_config.get("target_ci_width", 20.0)
        self.min_queries = config.get("tracking", {}).get("queries_per_prompt", 10)
        self.max_queries = adaptive_config.get("max_queries", 200)
        self.check_interval = adaptive_config.get("check_interval", 5)
        self.convergence_scope = adaptive_config.get("convergence_scope", "primary_brand")
        self.confidence_level = (
            config.get("tracking", {}).get("statistical_analysis", {}).get("confidence_level", 95)
        )
        self.ci_strategy = WilsonCIStrategy()
        self._stats: Dict[str, RunningStats] = {}

    def _key(self, model: str, prompt: str, brand: str) -> str:
        return f"{model}::{prompt}::{brand}"

    def record(self, model: str, prompt: str, brand: str, score: float) -> None:
        k = self._key(model, prompt, brand)
        if k not in self._stats:
            self._stats[k] = RunningStats(self.ci_strategy, self.confidence_level)
        self._stats[k].record(score)

    def get_stats(self, model: str, prompt: str, brand: str) -> Optional[RunningStats]:
        return self._stats.get(self._key(model, prompt, brand))

    def should_stop(
        self, model: str, prompt: str, primary_brand: str, all_brands: Optional[List[str]] = None
    ) -> bool:
        if self.convergence_scope == "primary_brand":
            stats = self.get_stats(model, prompt, primary_brand)
            if stats is None:
                return False
            return stats.converged(self.target_ci_width, self.min_queries)
        elif self.convergence_scope == "all_tracked_brands":
            brands = all_brands or [primary_brand]
            for brand in brands:
                stats = self.get_stats(model, prompt, brand)
                if stats is None or not stats.converged(self.target_ci_width, self.min_queries):
                    return False
            return True
        return False

    def estimate_remaining(self, model: str, prompt: str, brand: str) -> Optional[int]:
        stats = self.get_stats(model, prompt, brand)
        if stats is None:
            return self.max_queries
        est = stats.estimate_queries_to_converge(self.target_ci_width)
        if est is None:
            return self.max_queries
        return min(est, self.max_queries)

    def get_status(
        self, primary_brand: str, all_brands: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        pairs: List[Dict[str, Any]] = []
        models_prompts: Dict[str, Dict[str, Any]] = {}

        for k, stats in self._stats.items():
            parts = k.split("::", 2)
            if len(parts) != 3:
                continue
            model, prompt, brand = parts
            mp_key = f"{model}::{prompt}"
            if mp_key not in models_prompts:
                models_prompts[mp_key] = {
                    "model": model,
                    "prompt": prompt,
                    "brands": {},
                    "queries_completed": 0,
                    "converged": False,
                }

            pair_info = {
                "brand": brand,
                "queries_completed": stats.n,
                "mean_score": round(stats.mean_score, 2),
                "ci_width": round(stats.ci_width, 2) if stats.ci_width else None,
                "ci": (round(stats.ci[0], 2), round(stats.ci[1], 2)) if stats.ci else None,
                "converged": stats.converged(self.target_ci_width, self.min_queries),
            }
            models_prompts[mp_key]["brands"][brand] = pair_info
            if brand == primary_brand:
                models_prompts[mp_key]["queries_completed"] = stats.n
                models_prompts[mp_key]["converged"] = pair_info["converged"]
                models_prompts[mp_key]["ci_width"] = pair_info["ci_width"]

            pairs.append(
                {
                    "model": model,
                    "prompt": prompt,
                    "brand": brand,
                    **pair_info,
                }
            )

        total_pairs = len(models_prompts)
        converged_pairs = sum(1 for v in models_prompts.values() if v["converged"])
        total_queries = sum(v["queries_completed"] for v in models_prompts.values())
        max_possible = total_pairs * self.max_queries

        return {
            "adaptive_enabled": True,
            "target_ci_width": self.target_ci_width,
            "max_queries": self.max_queries,
            "convergence_scope": self.convergence_scope,
            "overall_converged": converged_pairs == total_pairs and total_pairs > 0,
            "pairs": pairs,
            "summary": {
                "total_pairs": total_pairs,
                "converged_pairs": converged_pairs,
                "total_queries": total_queries,
                "estimated_queries_saved": max(0, max_possible - total_queries),
            },
        }


class AnalyticsEngine:
    """Analytics and reporting engine with statistical analysis."""

    Z_SCORES = {90: 1.645, 95: 1.96, 99: 2.576}  # Common confidence levels

    def __init__(self, db: TrackDatabase):
        self.db = db

    def _calculate_confidence_interval(
        self, proportion: float, sample_size: int, confidence_level: float = 95.0
    ) -> Optional[tuple]:
        """Calculate Wilson score confidence interval for proportions.

        Args:
            proportion: Observed proportion (mentions/total)
            sample_size: Number of trials
            confidence_level: 90, 95, or 99

        Returns:
            (lower_bound, upper_bound) as percentages, or None if no data
        """
        if sample_size == 0 or proportion == 0:
            return None

        z = self.Z_SCORES.get(int(confidence_level), 1.96)
        n = sample_size
        p = proportion / 100.0  # Convert to 0-1 scale

        # Wilson score interval
        denominator = 1 + z**2 / n
        centre_adjusted_probability = (p + z**2 / (2 * n)) / denominator
        adjusted_standard_deviation = (
            z * math.sqrt((p * (1 - p) + z**2 / (4 * n)) / n)
        ) / denominator

        lower = (centre_adjusted_probability - adjusted_standard_deviation) * 100
        upper = (centre_adjusted_probability + adjusted_standard_deviation) * 100

        return (max(0, lower), min(100, upper))

    def calculate_variance(
        self, brand_keyword: str, days: int = 30, confidence_level: float = 95
    ) -> Dict[str, Dict[str, Any]]:
        """Calculate mention rate with confidence intervals per model."""
        stats = self.db.get_model_statistics(brand_keyword, days)

        if not stats:
            return {}

        variance_data = {}
        for model_stat in stats:
            mention_rate = model_stat["mention_rate_pct"]
            total_runs = model_stat["total_runs"]

            ci = self._calculate_confidence_interval(mention_rate, total_runs, confidence_level)

            variance_data[model_stat["model_name"]] = {
                "mention_rate": mention_rate,
                "total_runs": total_runs,
                "total_mentions": model_stat["total_mentions"],
                "confidence_interval_95": ci,
                "standard_error": (
                    math.sqrt((mention_rate / 100) * (1 - mention_rate / 100) / total_runs) * 100
                    if total_runs > 0
                    else 0
                ),
            }

        return variance_data

    def get_trends(self, brand_keyword: str, days: int = 30) -> List[Dict[str, Any]]:
        """Get trend data for a brand."""
        return self.db.get_trends(brand_keyword, days)

    def compare_models(self, brand_keyword: str, days: int = 30) -> List[Dict[str, Any]]:
        """Compare models for a brand."""
        return self.db.get_model_statistics(brand_keyword, days)

    def get_all_mentions(self, days: int = 90) -> List[Dict[str, Any]]:
        """Get all mentions across all brands."""
        return self.db.get_all_mentions(days)

    def get_summary(self, brand_keyword: str, days: int = 30) -> Dict[str, Any]:
        """Get summary statistics for a brand."""
        stats = self.db.get_model_statistics(brand_keyword, days)

        if not stats:
            return {
                "brand": brand_keyword,
                "period_days": days,
                "total_mentions": 0,
                "total_queries": 0,
                "overall_mention_rate": 0.0,
                "variance_by_model": {},
            }

        total_mentions = sum(s["total_mentions"] for s in stats)
        total_queries = sum(s["total_runs"] for s in stats)
        overall_rate = (total_mentions / total_queries * 100) if total_queries > 0 else 0

        variance_data = {}
        for model_stat in stats:
            variance_data[model_stat["model_name"]] = {
                "mention_rate": model_stat["mention_rate_pct"],
                "total_runs": model_stat["total_runs"],
                "total_mentions": model_stat["total_mentions"],
            }

        return {
            "brand": brand_keyword,
            "period_days": days,
            "total_mentions": total_mentions,
            "total_queries": total_queries,
            "overall_mention_rate": round(overall_rate, 2),
            "variance_by_model": variance_data,
        }

    def get_visibility_score(self, brand_keyword: str, days: int = 30) -> Dict[str, Any]:
        """Calculate overall visibility score for a brand.

        Returns:
            Dictionary with score, total prompts, successful prompts, and per-model breakdown.
        """
        trends = self.db.get_trends(brand_keyword, days, group_by_day=False)

        if not trends:
            return {
                "brand": brand_keyword,
                "score": 0.0,
                "total_prompts": 0,
                "successful_prompts": 0,
                "by_model": [],
                "confidence_interval": None,
            }

        total_prompts = sum(t["total_queries"] for t in trends)
        successful_prompts = sum(t["mention_count"] for t in trends)

        score = (successful_prompts / total_prompts * 100) if total_prompts > 0 else 0.0

        # Calculate confidence interval
        ci = self._calculate_confidence_interval(score, total_prompts)

        # Per-model breakdown
        by_model = []
        for model_stat in self.db.get_model_statistics(brand_keyword, days):
            model_total = model_stat["total_runs"]
            model_mentions = model_stat["total_mentions"]
            model_score = (model_mentions / model_total * 100) if model_total > 0 else 0.0
            model_ci = self._calculate_confidence_interval(model_score, model_total)

            by_model.append(
                {
                    "model_name": model_stat["model_name"],
                    "model_provider": model_stat["model_provider"],
                    "score": round(model_score, 2),
                    "total_prompts": model_total,
                    "successful_prompts": model_mentions,
                    "confidence_interval": model_ci,
                }
            )

        return {
            "brand": brand_keyword,
            "score": round(score, 2),
            "total_prompts": total_prompts,
            "successful_prompts": successful_prompts,
            "by_model": by_model,
            "confidence_interval": ci,
        }

    def get_competitor_comparison(self, target_brand: str, days: int = 30) -> Dict[str, Any]:
        """Compare target brand mention rates against competitors.

        Args:
            target_brand: The target brand to compare
            days: Lookback period in days

        Returns:
            Dictionary with comparison data including all brands and their mention rates.
        """
        # Load brands config to get competitor list
        import yaml
        from pathlib import Path

        config_file = Path("configs/default.yaml")
        if config_file.exists():
            with open(config_file, "r") as f:
                config = yaml.safe_load(f)

            # Merge brand configs
            if "tool" in config and "users" in config:
                users_path = config_file.parent / config["users"].lstrip("/")
                brands_file = users_path / "brands.yaml"
                if brands_file.exists():
                    with open(brands_file, "r") as bf:
                        user_config = yaml.safe_load(bf)
                        brands_config = user_config.get("brands", [])
                else:
                    brands_config = config.get("brands", [])
            else:
                brands_config = config.get("brands", [])
        else:
            brands_config = []

        # Find target brand and its competitors
        target_data = None
        competitors_data = []

        for brand in brands_config:
            if brand["name"] == target_brand:
                target_data = brand
                # Get competitors from target brand
                for competitor in brand.get("competitors", []):
                    competitors_data.append(
                        {
                            "name": competitor["name"],
                            "keywords": competitor.get("keywords", [competitor["name"]]),
                        }
                    )
                break

        if not target_data:
            return {
                "target_brand": target_brand,
                "target_score": 0.0,
                "competitors": [],
                "period_days": days,
            }

        # Get mention rates for target brand
        target_stats = self.db.get_model_statistics(target_brand, days)
        total_target = sum(s["total_runs"] for s in target_stats)
        total_target_mentions = sum(s["total_mentions"] for s in target_stats)
        target_score = (total_target_mentions / total_target * 100) if total_target > 0 else 0.0

        # Get mention rates for all competitors
        competitors_comparison = []
        all_brands_names = set()

        for comp in competitors_data:
            comp_name = comp["name"]
            all_brands_names.add(comp_name)

            comp_stats = self.db.get_model_statistics(comp_name, days)
            comp_total = sum(s["total_runs"] for s in comp_stats)
            comp_mentions = sum(s["total_mentions"] for s in comp_stats)
            comp_score = (comp_mentions / comp_total * 100) if comp_total > 0 else 0.0

            competitors_comparison.append(
                {
                    "name": comp_name,
                    "score": round(comp_score, 2),
                    "total_prompts": comp_total,
                    "successful_prompts": comp_mentions,
                    "mention_count": comp_mentions,
                }
            )

        # Also include target brand in the full list
        all_brands = [
            {
                "name": target_brand,
                "score": round(target_score, 2),
                "total_prompts": total_target,
                "successful_prompts": total_target_mentions,
                "is_target": True,
            }
        ]
        all_brands.extend(competitors_comparison)

        # Sort by score descending
        all_brands.sort(key=lambda x: x["score"], reverse=True)

        return {
            "target_brand": target_brand,
            "target_score": round(target_score, 2),
            "competitors": competitors_comparison,
            "all_brands": all_brands,
            "period_days": days,
        }

    def get_prompt_list(
        self,
        brand_keyword: str,
        model_name: Optional[str] = None,
        days: int = 30,
        success_filter: Optional[bool] = None,
        page: int = 1,
        limit: int = 25,
    ) -> Dict[str, Any]:
        """Get detailed list of prompts tested for a brand.

        Args:
            brand_keyword: Brand to filter by
            model_name: Optional model filter
            days: Lookback period
            success_filter: Filter by success (True) or failure (False), or None for all
            page: Page number (1-indexed)
            limit: Items per page

        Returns:
            Dictionary with prompts list, pagination info, and totals.
        """
        conn = self.db._get_connection()
        cursor = conn.cursor()

        try:
            cutoff = datetime.utcnow() - timedelta(days=days)

            # Build query
            query = """
                SELECT 
                    id,
                    run_id,
                    model_provider,
                    model_name,
                    prompt,
                    response_text,
                    mentions_json,
                    detected_at
                FROM visibility_records
                WHERE detected_at > ?
                AND mentions_json LIKE ?
            """
            params = [cutoff, f'%"{brand_keyword}%']

            if model_name:
                query += " AND model_name = ?"
                params.append(model_name)

            # Success filter: TRUE = has other brands mentioned, FALSE = only target brand or none
            if success_filter is not None:
                if success_filter:
                    # Successful = target brand mentioned AND at least one other brand
                    query += """
                        AND (
                            LENGTH(mentions_json) > 2 
                            AND mentions_json != ?
                        )
                    """
                    params.append(f'{{"{brand_keyword}": ')
                else:
                    # Failed = no mentions or only target brand
                    query += """
                        AND (
                            mentions_json = '{}'
                            OR mentions_json = ?
                            OR mentions_json LIKE ?
                        )
                    """
                    params.extend([f'{{"{brand_keyword}": 1}}', f'{{"{brand_keyword}": 1,%'])

            query += " ORDER BY detected_at DESC"

            # Add pagination
            offset = (page - 1) * limit
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            rows = cursor.fetchall()

            # Get total count for pagination
            count_query = """
                SELECT COUNT(*) FROM visibility_records
                WHERE detected_at > ?
                AND mentions_json LIKE ?
            """
            count_params = [cutoff, f'%"{brand_keyword}%']

            if model_name:
                count_query += " AND model_name = ?"
                count_params.append(model_name)

            cursor.execute(count_query, count_params)
            total = cursor.fetchone()[0]

            # Format results
            prompts = []
            for row in rows:
                mentions = json.loads(row["mentions_json"] or "{}")
                is_success = len(mentions) > 1  # Success if more than one brand mentioned
                prompts.append(
                    {
                        "id": row["id"],
                        "run_id": row["run_id"],
                        "model_provider": row["model_provider"],
                        "model_name": row["model_name"],
                        "prompt": row["prompt"],
                        "response_text": row["response_text"],
                        "mentions": mentions,
                        "detected_at": row["detected_at"],
                        "is_success": is_success,
                    }
                )

            return {
                "prompts": prompts,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "total_pages": (total + limit - 1) // limit,
                },
                "filters": {
                    "brand": brand_keyword,
                    "model": model_name,
                    "days": days,
                    "success_filter": success_filter,
                },
            }
        finally:
            conn.close()

    def get_prompt_detail(self, record_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed information for a single prompt result.

        Args:
            record_id: The visibility_records ID

        Returns:
            Dictionary with full prompt details and highlighted mentions, or None.
        """
        conn = self.db._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT 
                    id,
                    run_id,
                    model_provider,
                    model_name,
                    prompt,
                    response_text,
                    mentions_json,
                    detected_at
                FROM visibility_records
                WHERE id = ?
            """,
                (record_id,),
            )

            row = cursor.fetchone()
            if not row:
                return None

            mentions = json.loads(row["mentions_json"] or "{}")

            # Load brands config for highlighting
            import yaml
            from pathlib import Path

            config_file = Path("configs/default.yaml")
            brands = {}

            if config_file.exists():
                with open(config_file, "r") as f:
                    config = yaml.safe_load(f)

                if "tool" in config and "users" in config:
                    users_path = config_file.parent / config["users"].lstrip("/")
                    brands_file = users_path / "brands.yaml"
                    if brands_file.exists():
                        with open(brands_file, "r") as bf:
                            user_config = yaml.safe_load(bf)
                            for brand in user_config.get("brands", []):
                                brands[brand["name"]] = {
                                    "keywords": brand.get("keywords", []),
                                    "is_target": False,
                                }
                                # Add competitors
                                for comp in brand.get("competitors", []):
                                    brands[comp["name"]] = {
                                        "keywords": comp.get("keywords", [comp["name"]]),
                                        "is_target": False,
                                    }

            # Determine target brand from mentions or context
            target_brand = None
            # For now, assume first mentioned brand is the "success" target
            if mentions:
                target_brand = list(mentions.keys())[0]

            # Create highlighted response text
            highlighted_text = self._highlight_mentions(
                row["response_text"] or "", mentions, target_brand, brands
            )

            return {
                "id": row["id"],
                "run_id": row["run_id"],
                "model_provider": row["model_provider"],
                "model_name": row["model_name"],
                "prompt": row["prompt"],
                "response_text": row["response_text"],
                "highlighted_response": highlighted_text,
                "mentions": mentions,
                "detected_at": row["detected_at"],
                "target_brand": target_brand,
            }
        finally:
            conn.close()

    def _highlight_mentions(
        self,
        text: str,
        mentions: Dict[str, int],
        target_brand: Optional[str],
        brands: Dict[str, dict],
    ) -> str:
        """Create HTML with highlighted brand mentions.

        Args:
            text: Response text to highlight
            mentions: Dictionary of brand mentions
            target_brand: The primary brand (target)
            brands: All brands config

        Returns:
            HTML string with highlighted mentions.
        """
        result = text

        # Sort by keyword length (longest first) to avoid partial replacements
        all_keywords = []
        for brand_name, config in brands.items():
            is_target = brand_name == target_brand
            for keyword in config.get("keywords", []):
                all_keywords.append(
                    {"keyword": keyword, "brand": brand_name, "is_target": is_target}
                )

        all_keywords.sort(key=lambda x: len(x["keyword"]), reverse=True)

        # Replace each keyword with highlighted version
        for kw_info in all_keywords:
            keyword = kw_info["keyword"]
            brand = kw_info["brand"]
            is_target = kw_info["is_target"]
            is_mentioned = brand in mentions

            # Escape HTML in keyword
            escaped_keyword = re.escape(keyword)

            if is_mentioned:
                # Highlighted color: green for target, orange for competitors
                color = "green" if is_target else "#f59e0b"
                replacement = f'<mark style="background-color: {color}33; color: {color}; font-weight: bold;">{keyword}</mark>'
            else:
                replacement = keyword

            # Case-insensitive replacement
            result = re.sub(rf"\b{escaped_keyword}\b", replacement, result, flags=re.IGNORECASE)

        return result

    def get_run_history(self, days: int = 30, limit: int = 20) -> List[Dict[str, Any]]:
        """Get history of tracking runs with summary statistics.

        Args:
            days: Lookback period
            limit: Maximum runs to return

        Returns:
            List of run records with summary stats.
        """
        recent_runs = self.db.get_recent_runs(days)

        run_history = []
        for run in recent_runs[:limit]:
            # Get records for this run
            records = self.db.get_by_run(run["id"])

            # Calculate run statistics
            total_queries = len(records)
            successful_queries = sum(
                1 for r in records if r["mentions_json"] and r["mentions_json"] != "{}"
            )

            # Get models used
            models_used = list(set(r["model_name"] for r in records))

            # Parse mentions for all brands
            all_mentions = defaultdict(int)
            for record in records:
                mentions = json.loads(record["mentions_json"] or "{}")
                for brand, count in mentions.items():
                    all_mentions[brand] += count

            run_history.append(
                {
                    "run_id": run["id"],
                    "started_at": run["started_at"],
                    "completed_at": run["completed_at"],
                    "duration": None,
                    "total_queries": total_queries,
                    "successful_queries": successful_queries,
                    "success_rate": (successful_queries / total_queries * 100)
                    if total_queries > 0
                    else 0,
                    "models_used": models_used,
                    "all_mentions": dict(all_mentions),
                }
            )

        # Calculate durations
        for run in run_history:
            if run["completed_at"] and run["started_at"]:
                start = run["started_at"]
                end = run["completed_at"]
                if hasattr(start, "strftime"):
                    run["duration"] = str(end - start)

        return run_history

    def get_run_comparison(self, brand_keyword: str, days: int = 30) -> Dict[str, Any]:
        """Compare run-to-run trend to detect drift or anomalies."""
        # Direct implementation for run comparison
        runs = self.get_run_history(days)

        if not runs:
            return {
                "brand": brand_keyword,
                "runs_analyzed": 0,
                "message": "No runs to compare",
            }

        run_trends = []
        for run in runs:
            records = self.db.get_by_run(run["run_id"])
            total = len(records)
            mentions = sum(
                1 for r in records if brand_keyword in json.loads(r["mentions_json"] or "{}")
            )
            rate = (mentions / total * 100) if total > 0 else 0

            run_trends.append(
                {
                    "run_id": run["run_id"],
                    "started_at": run["started_at"],
                    "completed_at": run["completed_at"],
                    "total_queries": total,
                    "brand_mentions": mentions,
                    "mention_rate": round(rate, 2),
                }
            )

        return {
            "brand": brand_keyword,
            "runs_analyzed": len(runs),
            "run_trends": run_trends,
        }

    def calculate_statistical_summary(self, brand_keyword: str, days: int = 30) -> Dict[str, Any]:
        """Calculate comprehensive stats with confidence intervals.

        Args:
            brand_keyword: Brand to analyze
            days: Lookback period

        Returns:
            Comprehensive statistical analysis for dashboard integration.
        """
        # Get all models' statistics
        stats = self.db.get_model_statistics(brand_keyword, days)

        if not stats:
            return {
                "brand": brand_keyword,
                "period_days": days,
                "n_models": 0,
                "message": "No data found",
            }

        # Calculate per-model statistics with CI
        model_stats = []
        for model_stat in stats:
            mention_rate = model_stat["mention_rate_pct"]
            total_runs = model_stat["total_runs"]

            # Calculate Wilson score CI
            ci = self._calculate_confidence_interval(mention_rate, total_runs, 95)

            # Calculate standard error
            std_err = (
                math.sqrt((mention_rate / 100) * (1 - mention_rate / 100) / total_runs) * 100
                if total_runs > 0
                else 0
            )

            model_stats.append(
                {
                    "model_name": model_stat["model_name"],
                    "mention_rate": mention_rate,
                    "total_runs": total_runs,
                    "mentions": model_stat["total_mentions"],
                    "confidence_interval_lower": round(ci[0] if ci else 0, 2),
                    "confidence_interval_upper": round(ci[1] if ci else 100, 2),
                    "standard_error": round(std_err, 2) if std_err else 0,
                    "statistical_significance": "N/A"
                    if total_runs < 30
                    else self._assess_significance(mention_rate, std_err, total_runs),
                }
            )

        # Calculate aggregate statistics
        total_mentions = sum(s["mentions"] for s in model_stats)
        total_runs = sum(s["total_runs"] for s in model_stats)
        overall_rate = (total_mentions / total_runs * 100) if total_runs > 0 else 0

        aggregate_ci = self._calculate_confidence_interval(overall_rate, total_runs, 95)

        return {
            "brand": brand_keyword,
            "period_days": days,
            "n_models": len(model_stats),
            "n_runs": total_runs,
            "overall_mention_rate": round(overall_rate, 2),
            "model_stats": model_stats,
            "aggregate_ci": aggregate_ci,
            "interpretation": self._interpret_aggregate_stats(overall_rate, total_runs),
        }

    def _assess_significance(
        self,
        mention_rate: float,
        std_error: float,
        total_runs: int,
        min_significant_change: float = 1.645,
    ) -> str:
        """Assess if brand visibility is distinguishable at a given level.

        Uses coefficient of variation and number of samples to assess statistical confidence.
        """
        if total_runs < 30 or std_error == 0:
            return "Insufficient data"

        # Assess if the brand visibility rate is well established, not just noise
        # Uses z-score relative to confidence interval width
        if mention_rate <= 0:
            z_equiv = 0
        else:
            # Calculate how many standard errors from zero the observation is
            z_equiv = mention_rate / std_error

        # Use appropriate threshold based on confidence
        if z_equiv > min_significant_change:
            return f"Statistically distinguishable (${z_equiv:.1f}\u03c3)"
        elif z_equiv > 0.5:
            return f"Possible signal (${z_equiv:.1f}\u03c3)"
        else:
            return "Within noise (\u00b10.5\u03c3)"

    def _interpret_aggregate_stats(self, rate: float, total_runs: int) -> str:
        """Generate user-friendly interpretation of aggregate stats."""
        interpretations = []

        # Sample size
        if total_runs < 30:
            interpretations.append("Limited data - more samples recommended")
        elif total_runs < 50:
            interpretations.append("Good sample size - reliable insights")
        else:
            interpretations.append("Strong data foundation - statistically robust")

        # Rate interpretation
        if rate < 30:
            interpretations.append("Low brand visibility - consider campaign improvement")
        elif rate < 60:
            interpretations.append("Moderate visibility - steady performance")
        else:
            interpretations.append("Strong visibility - brand performing well")

        return "; ".join(interpretations)

    def get_statistical_summary(self, brand_keyword: str, days: int = 30) -> Dict[str, Any]:
        """Calculate comprehensive statistical summary for a brand.

        Includes mean, standard deviation, confidence intervals,
        and run-to-run variance.

        Args:
            brand_keyword: Brand to analyze
            days: Lookback period

        Returns:
            Dictionary with comprehensive statistical metrics.
        """
        # Get all runs in period
        runs = self.get_run_history(days)

        if not runs:
            return {
                "brand": brand_keyword,
                "period_days": days,
                "n_runs": 0,
                "message": "No runs found",
            }

        # Calculate mention rate per run
        run_rates = []
        for run in runs:
            # Count mentions of this brand in this run
            brand_mentions = sum(
                1
                for r in self.db.get_by_run(run["run_id"])
                if brand_keyword in (json.loads(r["mentions_json"] or "{}"))
            )
            total = run["total_queries"]
            rate = (brand_mentions / total * 100) if total > 0 else 0
            run_rates.append(rate)

        if not run_rates:
            return {
                "brand": brand_keyword,
                "period_days": days,
                "n_runs": len(runs),
                "message": "No data for brand",
            }

        # Calculate statistics
        n = len(run_rates)
        mean_rate = sum(run_rates) / n
        variance = sum((r - mean_rate) ** 2 for r in run_rates) / (n - 1) if n > 1 else 0
        std_dev = math.sqrt(variance)
        std_error = std_dev / math.sqrt(n) if n > 0 else 0

        # 95% confidence interval
        ci = self._calculate_confidence_interval(mean_rate, n)

        # Coefficient of variation (measures stability)
        cv = (std_dev / mean_rate * 100) if mean_rate > 0 else 0

        # Identify significant changes (>2 std from mean)
        anomalies = []
        for i, rate in enumerate(run_rates):
            if abs(rate - mean_rate) > 2 * std_dev:
                anomalies.append(
                    {
                        "run_index": i,
                        "run_id": runs[i]["run_id"],
                        "rate": rate,
                        "deviation": (rate - mean_rate) / std_dev if std_dev > 0 else 0,
                    }
                )

        return {
            "brand": brand_keyword,
            "period_days": days,
            "n_runs": n,
            "mean_mention_rate": round(mean_rate, 2),
            "std_deviation": round(std_dev, 2),
            "std_error": round(std_error, 2),
            "confidence_interval_95": ci,
            "coefficient_of_variation": round(cv, 2),
            "min_rate": min(run_rates),
            "max_rate": max(run_rates),
            "rate_range": max(run_rates) - min(run_rates),
            "anomalies": anomalies,
            "interpretation": self._interpret_statistics(cv, n, std_dev),
        }

    def _interpret_statistics(self, cv: float, n: int, std_dev: float) -> str:
        """Interpret statistical metrics for user-friendly display."""
        interpretations = []

        # Stability assessment
        if cv < 10:
            interpretations.append("Very stable performance")
        elif cv < 20:
            interpretations.append("Stable performance with minor variation")
        elif cv < 30:
            interpretations.append("Moderate variation detected")
        else:
            interpretations.append("High variation - investigate causes")

        # Sample size assessment
        if n < 5:
            interpretations.append("Limited data points - confidence will be lower")
        elif n < 10:
            interpretations.append("Adequate sample size for preliminary insights")
        else:
            interpretations.append("Strong sample size for reliable conclusions")

        return "; ".join(interpretations)

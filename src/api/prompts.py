"""API routes for prompt data and statistics."""

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import yaml
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from src.storage import TrackDatabase

router = APIRouter(prefix="/api", tags=["Data"])


def load_config() -> dict:
    """Load application configuration."""
    config_path = Path("configs/default.yaml")
    if not config_path.exists():
        raise HTTPException(status_code=404, detail="Configuration not found")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def load_brands() -> list:
    """Load brand configuration."""
    brands_path = Path("configs/users/brands.yaml")
    if not brands_path.exists():
        raise HTTPException(status_code=404, detail="Brands configuration not found")
    with open(brands_path, "r") as f:
        return yaml.safe_load(f).get("brands", [])


def detect_mentions(text: str, brands: list) -> dict:
    """Detect which brands are mentioned in text."""
    mentions = {}
    for brand in brands:
        brand_keywords = brand.get("keywords", [])
        for keyword in brand_keywords:
            if keyword.lower() in text.lower():
                mentions[brand["name"]] = mentions.get(brand["name"], 0) + 1
    return mentions


# === Existing Data Route ===
@router.get(
    "/data",
    response_model=dict,
    summary="Get brand statistics and trends",
    description="Retrieves mention statistics and trends for a specific brand",
)
async def get_data(
    brand: str = Query(..., description="Brand name to analyze"),
    days: int = Query(90, description="Days of history to analyze", gt=0),
) -> dict:
    """Get comprehensive brand statistics."""
    db = TrackDatabase()
    trends = db.get_trends(brand, days)

    if not trends:
        raise HTTPException(status_code=404, detail=f"No data found for brand: {brand}")

    # Calculate overall stats
    total_queries = len(trends)
    total_mentions = sum(row.get("mention_count", 0) for row in trends)

    return {
        "brand": brand,
        "period_days": days,
        "total_queries": total_queries,
        "total_mentions": total_mentions,
        "mention_rate": (total_mentions / total_queries * 100) if total_queries > 0 else 0,
        "by_model": trends,
    }


# === New: Visibility Score ===
@router.get(
    "/visibility-score",
    response_model=dict,
    summary="Get overall visibility score",
    description="Calculates visibility score for a brand (successful prompts / total prompts * 100)",
)
async def get_visibility_score(
    brand: str = Query(..., description="Brand name to analyze"),
    days: int = Query(30, description="Days of history", gt=0),
) -> dict:
    """
    Calculate visibility score for target brand.

    Visibility Score = (Successful Prompts / Total Prompts) × 100

    A prompt is successful if the target brand is mentioned.
    """
    db = TrackDatabase()
    brand_keywords = [b.get("keywords", []) for b in load_brands() if b["name"] == brand]

    # Get all mentions for this brand
    all_records = db.get_all_records()

    if not all_records:
        raise HTTPException(status_code=404, detail="No data found")

    total_prompts = 0  # Count unique prompts (not queries)
    successful_prompts = 0

    # Track unique prompts per brand mention
    brand_mentions = set()

    for record in all_records:
        if record["timestamp"] < datetime.utcnow() - timedelta(days=days):
            continue

        # Check if this record mentions our target brand
        mentions_str = record.get("mentions_str", "")
        if brand in mentions_str or any(
            kw in mentions_str for kw in brand_keywords[0] if brand_keywords
        ):
            prompt_key = f"{record.get('model', 'unknown')}:{record.get('prompt', 'unknown')}:{record['timestamp']}"
            brand_mentions.add(prompt_key)

    total_prompts = len(brand_mentions)
    successful_prompts = total_prompts  # All mentioned = successful

    visibility_score = (successful_prompts / total_prompts * 100) if total_prompts > 0 else 0

    return {
        "brand": brand,
        "period_days": days,
        "total_prompts": total_prompts,
        "successful_prompts": successful_prompts,
        "visibility_score": round(visibility_score, 2),
        "trend_indicator": "↑" if visibility_score > 70 else "→" if visibility_score > 50 else "↓",
    }


# === New: Competitors ===
@router.get(
    "/competitors",
    response_model=list,
    summary="Get competitor comparison",
    description="Comparative analysis of brand vs. competitors mention rates",
)
async def get_competitors(
    brand: str = Query(..., description="Target brand"),
    days: int = Query(30, description="Days of history", gt=0),
) -> list:
    """
    Get competitive comparison for target brand and all competitors.

    Shows mention rates for:
    - Target brand
    - All competitor brands configured in brands.yaml
    """
    db = TrackDatabase()
    brands = load_brands()

    # Separate target brand and competitors
    target_brand = next((b for b in brands if b["name"] == brand), None)
    if not target_brand:
        raise HTTPException(status_code=404, detail=f"Brand not found: {brand}")

    competitors = [b for b in brands if b["name"] != brand]

    # Get data for all brands
    brand_data = []
    for b in brands:
        trends = db.get_trends(b["name"], days)
        if not trends:
            continue

        total_queries = len(trends)
        total_mentions = sum(row.get("mention_count", 0) for row in trends)
        rate = (total_mentions / total_queries * 100) if total_queries > 0 else 0

        brand_data.append(
            {
                "brand": b["name"],
                "is_target": b["name"] == brand,
                "total_queries": total_queries,
                "total_mentions": total_mentions,
                "mention_rate": round(rate, 2),
            }
        )

    return sorted(brand_data, key=lambda x: x["mention_rate"], reverse=True)


# === New: Runs History ===
@router.get(
    "/run-history",
    response_model=list,
    summary="Get tracking run history",
    description="Lists all tracking runs with duration and success metrics",
)
async def get_run_history(days: int = Query(90, description="Days of run history", gt=0)) -> list:
    """
    Get history of tracking runs.

    Each run entry includes:
    - run_id
    - timestamp range
    - total queries
    - success/failure counts
    - duration
    - config hash (for reproducibility)
    """
    db = TrackDatabase()
    runs = db.get_all_runs()

    now = datetime.utcnow()
    cutoff = now - timedelta(days=days)

    filtered_runs = []
    for run in runs:
        if run.get("started_at") and run["started_at"] >= cutoff:
            # Convert ISO timestamp to datetime
            from datetime import datetime as dt

            started_dt = dt.fromisoformat(run["started_at"].replace("Z", "+00:00"))
            started_iso = started_dt.isoformat()

            # Parse completed timestamp if available
            completed_iso = run.get("completed_at")
            if completed_iso:
                completed_dt = dt.fromisoformat(completed_iso.replace("Z", "+00:00"))
                completed_iso = completed_dt.isoformat()

                # Calculate duration
                duration = (completed_dt - started_dt).total_seconds() / 3600
            else:
                continued_iso = run.get("started_at")
                duration = None

    return filtered_runs


@router.get(
    "/prompts",
    response_model=dict,
    summary="Get prompt results listing",
    description="Paginated list of all prompt results with filtering options",
)
async def get_prompts(
    brand: Optional[str] = None,
    model: Optional[str] = None,
    page: int = Query(1, ge=1, description="Page number for pagination", default=1),
    limit: int = Query(25, ge=5, le=100, description="Results per page", default=25),
    success_only: bool = Query(False, description="Only successful results", default=False),
    search: Optional[str] = None,
    days: int = Query(90, description="Days of history", gt=0),
) -> dict:
    """
    Get paginated list of prompt results.

    Filters:
    - brand: Filter by target brand
    - model: Filter by model provider
    - success_only: Only show successful results
    - search: Search in prompt text
    """
    db = TrackDatabase()
    all_records = db.get_all_records()

    brand_keywords = None
    if brand:
        brands = load_brands()
        target_brand = next((b for b in brands if b["name"] == brand), None)
        if target_brand:
            brand_keywords = target_brand.get("keywords", [])

    filtered = []
    for record in all_records:
        # Filter by date
        record_time = record.get("timestamp", "")
        if record_time:
            from datetime import datetime as dt

            try:
                record_dt = dt.fromisoformat(record_time.replace("Z", "+00:00"))
                if record_dt < (dt.utcnow() - timedelta(days=days)).replace(tzinfo=dt.utcnow()):
                    continue
            except:
                pass

        # Filter by brand
        if brand_keywords and brand:
            mentions_str = record.get("mentions_str", "")
            if not any(kw in mentions_str for kw in brand_keywords):
                continue

        # Filter by model
        if model:
            if "model_provider" not in record:
                continue
            if record["model_provider"] != model:
                continue

        # Filter by success
        if success_only:
            mentions_str = record.get("mentions_str", "")
            if not mentions_str or "mentioned > 0" not in mentions_str:
                continue

        # Search in prompt
        if search:
            if search.lower() not in record.get("prompt", "").lower():
                continue

        filtered.append(
            {
                "id": record.get("id"),
                "prompt": record.get("prompt", ""),
                "response": record.get("response_text", ""),
                "model": record.get("model_provider", ""),
                "model_name": record.get("model_name", ""),
                "timestamp": record.get("timestamp"),
                "mentions_str": record.get("mentions_str"),
                "success": bool(record.get("mentions_str", "")),
            }
        )

    # Paginate
    total = len(filtered)
    per_page = limit
    start = (page - 1) * per_page
    end = start + per_page

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
        "results": filtered[start:end],
    }


@router.get(
    "/prompts/{prompt_id}",
    response_model=dict,
    summary="Get prompt detail",
    description="Full details for a specific prompt result including mentions highlighted",
)
async def get_prompt_detail(prompt_id: int) -> dict:
    """
    Get detailed information for a specific prompt result.

    Returns:
    - Full response text
    - Parsed mention data (counts, positions)
    - Metadata (run ID, model, config hash)
    """
    db = TrackDatabase()
    record = db.get_record_by_id(prompt_id)

    if not record:
        raise HTTPException(status_code=404, detail=f"Prompt not found: {prompt_id}")

    return {
        "id": record.get("id"),
        "prompt": record.get("prompt", ""),
        "response": record.get("response_text", ""),
        "model": record.get("model_provider", ""),
        "model_name": record.get("model_name", ""),
        "run_id": record.get("run_id"),
        "timestamp": record.get("timestamp"),
        "mentions_str": record.get("mentions_str"),
        "config_hash": record.get("config_hash", ""),
    }


@router.get(
    "/statistical-summary",
    response_model=dict,
    summary="Get statistical summary",
    description="Calculates mean, std, CI, and other statistics over time period",
)
async def get_statistical_summary(
    brand: str = Query(..., description="Brand to analyze"),
    days: int = Query(30, description="Days of history", gt=0),
    ci_level: int = Query(95, description="Confidence level (90, 95, 99)", gt=80, le=99),
) -> dict:
    """
    Calculate comprehensive statistics with confidence intervals.

    Returns:
    - mean_rate: Average mention rate
    - std: Standard deviation
    - ci_[ci_level]: Confidence interval [lower, upper]
    - total_runs: Number of runs
    - total_queries: Total queries analyzed
    - sample_size_adq: Indicator if sample is adequate (std < 5)
    """
    db = TrackDatabase()
    trends = db.get_trends(brand, days)

    if not trends:
        raise HTTPException(status_code=404, detail=f"No data found for brand: {brand}")

    # Extract all mention rates
    mention_rates = [t.get("mention_rate", 0) for t in trends if t.get("mention_rate")]

    if not mention_rates:
        return {"brand": brand, "period_days": days, "error": "No valid mention rates found"}

    # Calculate basic statistics
    n = len(mention_rates)
    mean_rate = sum(mention_rates) / n

    # Standard deviation
    variance = sum((x - mean_rate) ** 2 for x in mention_rates) / n
    std = variance**0.5

    # Wilson score interval (simplified for large n)
    p = mean_rate / 100  # Convert % to proportion
    n_eff = n * (days / 30)  # Effective sample size
    z = 1.96 if ci_level == 95 else (1.645 if ci_level == 90 else 2.576)

    z_alpha = {90: 1.645, 95: 1.96, 99: 2.576}.get(ci_level, 1.96)
    se = z_alpha * ((p * (1 - p) / n_eff) ** 0.5)

    se_lower = se + z_alpha * ((p * (1 - p) / n_eff) ** 0.5)
    se_upper = se + z_alpha * ((p * (1 - p) / n_eff) ** 0.5)

    ci_lower = p - z_alpha * ((p * (1 - p) / n_eff) ** 0.5)
    ci_upper = p + z_alpha * ((p * (1 - p) / n_eff) ** 0.5)
    ci_lower = max(0, min(1, ci_lower)) * 100
    ci_upper = min(100, max(0, ci_upper)) * 100

    # By model
    by_model = {}
    for row in trends:
        model = row.get("model_name", "")
        if model:
            rates = [r.get("mention_rate", 0) for r in trends if r.get("model_name") == model]
            if rates:
                mean_m = sum(rates) / len(rates)
                std_m = (sum((x - mean_m) ** 2 for x in rates) / len(rates)) ** 0.5
                by_model[model] = {
                    "mean_rate": round(mean_m, 2),
                    "std": round(std_m, 2),
                    "queries": len(rates),
                }

    return {
        "brand": brand,
        "period_days": days,
        "overall": {
            "total_queries": sum(r.get("total_queries", 0) for r in trends),
            "mention_rate_mean": round(mean_rate, 2),
            "standard_deviation": round(std, 2),
            "coefficient_of_variation": round(std / mean_rate * 100, 2) if mean_rate > 0 else 0,
            "ci_level": ci_level,
            "ci_lower": round(ci_lower, 2),
            "ci_upper": round(ci_upper, 2),
            "total_runs": n,
            "sample_size_adq": std < 5 if n > 10 else False,  # Std < 5 & n > 10 = adequate
        },
        "by_model": by_model,
    }

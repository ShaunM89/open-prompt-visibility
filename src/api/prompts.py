"""API endpoints for prompt visibility tracking."""

import json
from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from src.storage import TrackDatabase
from src.analyzer import AnalyticsEngine, AdaptiveSampler

router = APIRouter()
_db = TrackDatabase()
_engine = AnalyticsEngine(_db)

_config: dict = {"brands": []}


@router.get("/data")
async def get_data_endpoint(
    brand: str = Query(..., description="Brand name to filter by"),
    days: int = Query(30, description="Number of days to look back"),
):
    """Get prompt results filtered by brand."""
    records = _db.get_all_records(brand, days)

    if not records:
        return {
            "total": 0,
            "results": [],
            "filters": {"brand": brand, "days": days},
        }

    response = []
    for record in records[:100]:
        record_data = {
            "id": record.get("record_id", record.get("id")),
            "prompt": record.get("prompt_text", record.get("prompt")),
            "model": record.get("model_name"),
            "run_id": record.get("run_id"),
            "timestamp": record.get("detected_at", record.get("timestamp")),
            "mentions": record.get("mentions_json", "{}"),
        }
        response.append(record_data)

    return {
        "total": len(records),
        "results": response,
        "filters": {"brand": brand, "days": days},
    }


@router.post("/run/start")
async def start_run(
    enable_variations: bool = Query(True, description="Enable prompt variations"),
    num_variations: int = Query(3, description="Number of variations per prompt"),
    variation_strategy: Optional[str] = Query("semantic", description="Variation strategy"),
):
    """Start a new tracking run with specified config options."""
    _config.setdefault("tracking", {}).setdefault("prompt_variations", {})["enabled"] = (
        enable_variations
    )
    _config["tracking"]["prompt_variations"]["num_variations"] = num_variations
    _config["tracking"]["prompt_variations"]["strategy"] = variation_strategy

    return {
        "status": "started",
        "config": _config,
    }


@router.get("/run-history")
async def get_recent_runs(
    days: int = Query(90, description="Number of days of runs to include"),
):
    """Get history of tracking runs."""
    return _db.get_recent_runs(days)[:10]


@router.get("/trends")
async def get_trends(
    brand: str = Query(..., description="Brand to get trend data for"),
    days: int = Query(30, description="Number of days of data"),
):
    """Get trend data for a brand."""
    return _db.get_trends(brand, days)


@router.get("/stats")
async def get_stats(
    brand: str = Query(..., description="Brand to get statistics for"),
    days: int = Query(30, description="Number of days to look back"),
):
    """Get statistical summary with confidence intervals."""
    return _engine.calculate_statistical_summary(brand, days)


@router.get("/models")
async def get_models(
    brand: str = Query(..., description="Brand to get model stats for"),
    days: int = Query(30, description="Number of days to look back"),
):
    """Get per-model statistics."""
    stats = _db.get_model_statistics(brand, days)
    model_stats = []
    for model_stat in stats:
        mention_rate = model_stat["mention_rate_pct"]
        total_runs = model_stat["total_runs"]
        ci = _engine._calculate_confidence_interval(mention_rate, total_runs, 95)
        std_err = (
            ((mention_rate / 100) * (1 - mention_rate / 100) / total_runs) ** 0.5 * 100
            if total_runs > 0
            else 0
        )
        model_stats.append(
            {
                "model_name": model_stat["model_name"],
                "mention_rate": round(mention_rate, 2),
                "total_runs": total_runs,
                "mentions": model_stat["total_mentions"],
                "confidence_interval": ci,
                "standard_error": round(std_err, 2),
                "statistical_significance": (
                    "N/A"
                    if total_runs < 30
                    else _engine._assess_significance(mention_rate, std_err, total_runs)
                ),
            }
        )
    model_stats.sort(key=lambda x: x["mention_rate"], reverse=True)

    return {"brand": brand, "models": model_stats}


@router.get("/competitors")
async def get_competitors(
    brand: str = Query(..., description="Brand to compare against competitors"),
    days: int = Query(30, description="Number of days to look back"),
):
    """Get competitor comparison data."""
    result = _engine.get_competitor_comparison(brand, days)

    if not result:
        return {
            "target_brand": brand,
            "target_score": 0,
            "competitors": [],
            "all_brands": [],
            "period_days": days,
        }

    if "all_brands" not in result:
        all_brands = [
            {
                "name": brand,
                "score": result.get("target_score", 0),
                "total_prompts": 0,
                "successful_prompts": 0,
                "is_target": True,
            }
        ]
        for c in result.get("competitors", []):
            c_copy = dict(c)
            c_copy["is_target"] = False
            all_brands.append(c_copy)
        all_brands.sort(key=lambda x: x.get("score", 0), reverse=True)
        result["all_brands"] = all_brands

    return result


@router.get("/export")
async def export_data(
    format: str = Query("json", description="Export format (csv, json)"),
    days: int = Query(90, description="Days of data to export"),
):
    """Export tracking data to file."""
    records = _db.get_all_records("*", days)

    export_records = []
    for record in records:
        export_records.append(
            {
                "record_id": record.get("record_id", record.get("id")),
                "timestamp": record.get("detected_at", record.get("timestamp")),
                "brand": record.get("brand_name", record.get("prompt")),
                "model": record.get("model_name"),
                "prompt": record.get("prompt", record.get("prompt_text")),
                "response": (record.get("response_text", "")[:200] + "...")
                if record.get("response_text")
                else "",
                "mentions": record.get("mentions_json", "{}"),
            }
        )

    return {
        "export_info": {
            "format": format,
            "days": days,
            "total_records": len(export_records),
            "exported_at": datetime.now().isoformat(),
        },
        "data": export_records,
    }


@router.get("/brands")
async def get_brands():
    """Get list of tracked brands from the database."""
    brands = _db.get_unique_brands()
    return {"brands": brands}


@router.get("/overview")
async def get_overview(
    brand: str = Query(..., description="Brand name"),
    days: int = Query(30, description="Number of days to look back"),
):
    """Get combined overview data for dashboard (stats + model stats + trends)."""
    stats = _db.get_stats()
    model_stats = _db.get_model_statistics(brand, days)
    trends = _db.get_trends(brand, days)
    return {"stats": stats, "modelStats": model_stats, "trends": trends}


@router.get("/visibility-score")
async def get_visibility_score(
    brand: str = Query(..., description="Brand to score"),
    days: int = Query(30, description="Number of days to look back"),
):
    """Get visibility score with per-model breakdown and confidence intervals."""
    model_stats = _db.get_model_statistics(brand, days)

    total_prompts = sum(m["total_runs"] for m in model_stats)
    successful_prompts = sum(m["total_mentions"] for m in model_stats)
    score = (successful_prompts / total_prompts * 100) if total_prompts > 0 else 0

    ci = _engine._calculate_confidence_interval(score, total_prompts, 95)

    by_model = []
    for m in model_stats:
        m_total = m["total_runs"]
        m_mentions = m["total_mentions"]
        m_score = (m_mentions / m_total * 100) if m_total > 0 else 0
        m_ci = _engine._calculate_confidence_interval(m_score, m_total, 95)
        by_model.append(
            {
                "model_name": m["model_name"],
                "model_provider": m["model_provider"],
                "score": round(m_score, 2),
                "total_prompts": m_total,
                "successful_prompts": m_mentions,
                "confidence_interval": m_ci,
            }
        )

    return {
        "brand": brand,
        "score": round(score, 2),
        "total_prompts": total_prompts,
        "successful_prompts": successful_prompts,
        "by_model": by_model,
        "confidence_interval": ci,
    }


@router.get("/prompt-list")
async def get_prompt_list(
    brand: str = Query(..., description="Brand to filter by"),
    days: int = Query(30, description="Number of days to look back"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(25, ge=1, le=100, description="Results per page"),
    model: Optional[str] = Query(None, description="Filter by model name"),
    success: Optional[bool] = Query(None, description="Filter by mention success"),
):
    """Get paginated prompt results for the dashboard."""
    records = _db.get_all_records(brand, days)

    filtered = []
    for r in records:
        mentions = (
            json.loads(r.get("mentions_json", "{}"))
            if isinstance(r.get("mentions_json"), str)
            else r.get("mentions_json", {})
        )
        is_success = len(mentions) > 0

        if model and r.get("model_name") != model:
            continue
        if success is not None and is_success != success:
            continue

        filtered.append(
            {
                "id": r.get("id"),
                "run_id": r.get("run_id"),
                "model_provider": r.get("model_provider", ""),
                "model_name": r.get("model_name", ""),
                "prompt": r.get("prompt", ""),
                "response_text": (r.get("response_text", "") or "")[:500],
                "mentions": mentions,
                "detected_at": str(r.get("detected_at", "")),
                "is_success": is_success,
            }
        )

    total = len(filtered)
    total_pages = max(1, (total + limit - 1) // limit)
    start = (page - 1) * limit
    page_results = filtered[start : start + limit]

    return {
        "prompts": page_results,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": total_pages,
        },
        "filters": {
            "brand": brand,
            "model": model,
            "days": days,
            "success_filter": success,
        },
    }


@router.get("/prompt-detail/{record_id}")
async def get_prompt_detail(record_id: int):
    """Get a single prompt record with full response text."""
    record = _db.get_record_by_id(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    return {
        "id": record["id"],
        "run_id": record["run_id"],
        "model_provider": record.get("model_provider", ""),
        "model_name": record.get("model_name", ""),
        "prompt": record.get("prompt", ""),
        "response_text": record.get("response", ""),
        "mentions": record.get("mentions", {}),
        "detected_at": str(record.get("timestamp", "")),
    }


@router.get("/run-history-detail")
async def get_run_history_detail(
    days: int = Query(90, description="Number of days of runs to include"),
):
    """Get detailed run history with per-run statistics."""
    runs = _db.get_all_runs(days)
    run_history = []
    for run in runs[:20]:
        records = _db.get_by_run(run["id"])
        total = len(records)
        successful = sum(
            1 for r in records if r.get("mentions_json") and r["mentions_json"] != "{}"
        )
        models_used = list({r.get("model_name", "") for r in records})
        success_rate = round(successful / total * 100, 2) if total > 0 else 0

        run_history.append(
            {
                "run_id": run["id"],
                "started_at": str(run.get("started_at", "")),
                "completed_at": str(run.get("completed_at", "")),
                "total_queries": total,
                "successful_queries": successful,
                "success_rate": success_rate,
                "models_used": models_used,
            }
        )

    return run_history


@router.get("/statistical-summary")
async def get_statistical_summary(
    brand: str = Query(..., description="Brand to analyze"),
    days: int = Query(30, description="Days of data to analyze"),
):
    """Get statistical summary with confidence intervals, variance, and anomaly detection."""
    runs = _db.get_all_runs(days)
    if not runs:
        return {
            "brand": brand,
            "period_days": days,
            "n_runs": 0,
            "message": "No runs found",
        }

    run_rates = []
    for run in runs:
        records = _db.get_by_run(run["id"])
        total = len(records)
        mentions = sum(
            1
            for r in records
            if brand
            in (
                json.loads(r.get("mentions_json", "{}"))
                if isinstance(r.get("mentions_json"), str)
                else r.get("mentions_json", {})
            )
        )
        rate = (mentions / total * 100) if total > 0 else 0
        run_rates.append(rate)

    if not run_rates:
        return {
            "brand": brand,
            "period_days": days,
            "n_runs": len(runs),
            "message": "No data for brand",
        }

    n = len(run_rates)
    mean_rate = sum(run_rates) / n
    variance = sum((r - mean_rate) ** 2 for r in run_rates) / (n - 1) if n > 1 else 0
    std_dev = variance**0.5
    std_error = std_dev / (n**0.5) if n > 0 else 0

    ci = _engine._calculate_confidence_interval(mean_rate, n, 95)
    cv = (std_dev / mean_rate * 100) if mean_rate > 0 else 0

    anomalies = []
    for i, rate in enumerate(run_rates):
        if std_dev > 0 and abs(rate - mean_rate) > 2 * std_dev:
            anomalies.append(
                {
                    "run_index": i,
                    "run_id": runs[i]["id"],
                    "rate": round(rate, 2),
                    "deviation": round((rate - mean_rate) / std_dev, 2),
                }
            )

    interpretation = "Stable" if cv < 20 else "Moderate variation" if cv < 30 else "High variation"

    return {
        "brand": brand,
        "period_days": days,
        "n_runs": n,
        "mean_mention_rate": round(mean_rate, 2),
        "std_deviation": round(std_dev, 2),
        "std_error": round(std_error, 2),
        "confidence_interval_95": ci,
        "coefficient_of_variation": round(cv, 2),
        "min_rate": round(min(run_rates), 2),
        "max_rate": round(max(run_rates), 2),
        "rate_range": round(max(run_rates) - min(run_rates), 2),
        "anomalies": anomalies,
        "interpretation": interpretation,
    }


@router.get("/sentiment")
async def get_sentiment(
    run_id: int = Query(..., description="Run ID to get sentiment for"),
):
    """Get sentiment analysis results for a run."""
    conn = _db._get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, run_metadata, started_at, completed_at FROM runs WHERE id = ?",
            (run_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

        metadata = {}
        raw = row["run_metadata"] if "run_metadata" in row.keys() else None
        if raw:
            try:
                metadata = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                pass

        sentiment = metadata.get("sentiment")

        if sentiment:
            return {
                "run_id": run_id,
                "mode": "fast",
                "started_at": str(row["started_at"]),
                "completed_at": str(row["completed_at"]),
                "brands": sentiment,
            }

        records = _db.get_by_run(run_id)
        detailed_sentiment = {}
        for record in records:
            mentions_raw = record.get("mentions_json", "{}")
            if isinstance(mentions_raw, str):
                mentions = _db._normalize_mentions(mentions_raw)
            else:
                mentions = mentions_raw

            for brand, data in mentions.items():
                if isinstance(data, dict) and "sentiment" in data:
                    if brand not in detailed_sentiment:
                        detailed_sentiment[brand] = []
                    detailed_sentiment[brand].append(data["sentiment"])

        if detailed_sentiment:
            brand_summaries = {}
            for brand, scores in detailed_sentiment.items():
                n = len(scores)
                avg_prom = sum(s.get("prominence", 0) for s in scores) / n
                avg_sent = sum(s.get("sentiment", 0) for s in scores) / n
                avg_comp = sum(s.get("composite", 0) for s in scores) / n
                brand_summaries[brand] = {
                    "avg_prominence": round(avg_prom, 3),
                    "avg_sentiment": round(avg_sent, 3),
                    "avg_composite": round(avg_comp, 3),
                    "sample_size": n,
                    "scores": scores,
                }

            return {
                "run_id": run_id,
                "mode": "detailed",
                "started_at": str(row["started_at"]),
                "completed_at": str(row["completed_at"]),
                "brands": brand_summaries,
            }

        return {
            "run_id": run_id,
            "mode": "none",
            "message": "No sentiment data available for this run",
        }
    finally:
        conn.close()


@router.get("/sentiment-latest")
async def get_sentiment_latest():
    """Get sentiment data for the latest completed run."""
    conn = _db._get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM runs WHERE completed_at IS NOT NULL ORDER BY id DESC LIMIT 1"
        )
        row = cursor.fetchone()
        if not row:
            return {"mode": "none", "message": "No completed runs found"}
        run_id = row["id"]
    finally:
        conn.close()
    return await get_sentiment(run_id=run_id)


@router.get("/convergence-status")
async def get_convergence_status(
    run_id: int = Query(..., description="Run ID to check convergence for"),
):
    """Get convergence status for a completed adaptive run."""
    conn = _db._get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, run_metadata FROM runs WHERE id = ?",
            (run_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

        metadata = {}
        raw = row["run_metadata"] if "run_metadata" in row.keys() else None
        if raw:
            try:
                metadata = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                pass

        convergence = metadata.get("convergence")
        sentiment = metadata.get("sentiment")
        if not convergence:
            return {
                "run_id": run_id,
                "adaptive_enabled": False,
                "message": "Run did not use adaptive sampling or has no convergence data",
            }

        result = {"run_id": run_id, **convergence}
        if sentiment:
            result["sentiment"] = sentiment
        return result
    finally:
        conn.close()


@router.get("/convergence-live")
async def get_convergence_live():
    """Get latest run convergence status (for frontend polling during active runs)."""
    conn = _db._get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, started_at, run_metadata FROM runs ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        if not row:
            return {"active": False, "message": "No runs found"}

        metadata = {}
        raw = row["run_metadata"] if "run_metadata" in row.keys() else None
        if raw:
            try:
                metadata = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                pass

        convergence = metadata.get("convergence")
        return {
            "active": convergence is not None,
            "run_id": row["id"],
            "convergence": convergence,
        }
    finally:
        conn.close()


# --- Segment Analysis Endpoints ---


@router.get("/visibility-by-segment")
async def get_visibility_by_segment(
    brand: str = Query(..., description="Brand to analyze"),
    dimension: str = Query(
        ..., description="Tag dimension: intent, purchase_stage, topic, or query_type"
    ),
    days: int = Query(30, description="Number of days to look back"),
):
    """Get mention rate per segment value for a given dimension."""
    valid_dimensions = ("intent", "purchase_stage", "topic", "query_type")
    if dimension not in valid_dimensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid dimension '{dimension}'. Must be one of: {valid_dimensions}",
        )

    segments = _db.get_visibility_by_segment(brand, dimension, days)

    # Add confidence intervals where possible
    for seg in segments:
        n = seg["total_queries"]
        p = seg["mention_rate"] / 100.0 if n > 0 else 0
        ci = _engine._calculate_confidence_interval(seg["mention_rate"], n, 95)
        seg["confidence_interval"] = ci

    return {
        "brand": brand,
        "dimension": dimension,
        "days": days,
        "segments": segments,
    }


@router.get("/segment-comparison")
async def get_segment_comparison(
    brands: str = Query(..., description="Comma-separated brand names"),
    dimension: str = Query(
        ..., description="Tag dimension: intent, purchase_stage, topic, or query_type"
    ),
    days: int = Query(30, description="Number of days to look back"),
):
    """Side-by-side mention rates per brand per segment."""
    valid_dimensions = ("intent", "purchase_stage", "topic", "query_type")
    if dimension not in valid_dimensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid dimension '{dimension}'. Must be one of: {valid_dimensions}",
        )

    brand_list = [b.strip() for b in brands.split(",") if b.strip()]
    if not brand_list:
        raise HTTPException(status_code=400, detail="At least one brand required")

    comparison = _db.get_segment_comparison(brand_list, dimension, days)

    # Add CIs
    for brand_key, segments in comparison.items():
        for seg in segments:
            ci = _engine._calculate_confidence_interval(
                seg["mention_rate"], seg["total_queries"], 95
            )
            seg["confidence_interval"] = ci

    return {
        "dimension": dimension,
        "days": days,
        "brands": comparison,
    }


@router.get("/variation-drift")
async def get_variation_drift(
    canonical_id: str = Query(..., description="Canonical prompt group ID"),
    brand: str = Query(..., description="Brand to check mentions for"),
    days: int = Query(30, description="Number of days to look back"),
):
    """Per-variation mention rates for a single canonical prompt group."""
    variations = _db.get_variation_drift(canonical_id, brand, days)

    # Calculate overall canonical rate
    total_queries = sum(v["total_queries"] for v in variations)
    total_mentions = sum(v["mention_count"] for v in variations)
    canonical_rate = (total_mentions / total_queries * 100) if total_queries > 0 else 0

    return {
        "canonical_id": canonical_id,
        "brand": brand,
        "days": days,
        "canonical_rate": round(canonical_rate, 2),
        "total_queries": total_queries,
        "variations": variations,
    }

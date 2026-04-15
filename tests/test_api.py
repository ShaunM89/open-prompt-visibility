"""Tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient

from src.api import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    from src.storage import TrackDatabase
    from src.analyzer import AnalyticsEngine
    from src.api import prompts as prompts_module

    test_db = TrackDatabase(db_path=str(tmp_path / "test.db"))

    run_id = test_db.create_run(config_hash="test_hash")
    for i in range(5):
        mentions = {"Nike": 1} if i < 4 else {}
        test_db.record_query(
            run_id=run_id,
            model_provider="ollama",
            model_name="qwen3.5",
            prompt=f"What are the best running shoes? ({i})",
            response_text=f"Response mentioning Nike shoes ({i})" if i < 4 else "Generic response",
            mentions=mentions,
        )

    test_db.complete_run(run_id)

    monkeypatch.setattr(prompts_module, "_db", test_db)
    monkeypatch.setattr(prompts_module, "_engine", AnalyticsEngine(test_db))

    return TestClient(app)


class TestOverviewEndpoint:
    def test_overview_returns_data(self, client):
        response = client.get("/overview?brand=Nike&days=30")
        assert response.status_code == 200
        data = response.json()
        assert "stats" in data
        assert "modelStats" in data
        assert "trends" in data

    def test_overview_stats_fields(self, client):
        response = client.get("/overview?brand=Nike&days=30")
        data = response.json()
        stats = data["stats"]
        assert "total_runs" in stats
        assert "total_records" in stats


class TestVisibilityScoreEndpoint:
    def test_visibility_score(self, client):
        response = client.get("/visibility-score?brand=Nike&days=30")
        assert response.status_code == 200
        data = response.json()
        assert "brand" in data
        assert "score" in data
        assert "total_prompts" in data
        assert "by_model" in data

    def test_visibility_score_has_ci(self, client):
        response = client.get("/visibility-score?brand=Nike&days=30")
        data = response.json()
        if data.get("confidence_interval"):
            ci = data["confidence_interval"]
            assert len(ci) == 2
            assert ci[0] < ci[1]


class TestPromptListEndpoint:
    def test_prompt_list(self, client):
        response = client.get("/prompt-list?brand=Nike&days=30")
        assert response.status_code == 200
        data = response.json()
        assert "prompts" in data
        assert "pagination" in data
        assert "filters" in data

    def test_prompt_list_pagination(self, client):
        response = client.get("/prompt-list?brand=Nike&days=30&page=1&limit=2")
        data = response.json()
        assert data["pagination"]["limit"] == 2
        assert len(data["prompts"]) <= 2

    def test_prompt_list_filter_success(self, client):
        response = client.get("/prompt-list?brand=Nike&days=30&success=true")
        data = response.json()
        for p in data["prompts"]:
            assert p["is_success"] is True


class TestPromptDetailEndpoint:
    def test_prompt_detail(self, client):
        list_resp = client.get("/prompt-list?brand=Nike&days=30")
        prompts = list_resp.json()["prompts"]
        if prompts:
            detail_resp = client.get(f"/prompt-detail/{prompts[0]['id']}")
            assert detail_resp.status_code == 200
            data = detail_resp.json()
            assert "id" in data
            assert "prompt" in data

    def test_prompt_detail_not_found(self, client):
        response = client.get("/prompt-detail/99999")
        assert response.status_code == 404


class TestCompetitorsEndpoint:
    def test_competitors(self, client):
        response = client.get("/competitors?brand=Nike&days=30")
        assert response.status_code == 200
        data = response.json()
        assert "target_brand" in data or "all_brands" in data


class TestStatisticalSummaryEndpoint:
    def test_statistical_summary(self, client):
        response = client.get("/statistical-summary?brand=Nike&days=30")
        assert response.status_code == 200
        data = response.json()
        assert "brand" in data
        assert "n_runs" in data


class TestRunHistoryEndpoint:
    def test_run_history_detail(self, client):
        response = client.get("/run-history-detail?days=30")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestBrandsEndpoint:
    def test_brands(self, client):
        response = client.get("/brands")
        assert response.status_code == 200
        data = response.json()
        assert "brands" in data


class TestStatsEndpoint:
    def test_stats(self, client):
        response = client.get("/stats?brand=Nike&days=30")
        assert response.status_code == 200


class TestSentimentEndpoint:
    def test_sentiment_no_data(self, client):
        response = client.get("/sentiment?run_id=99999")
        assert response.status_code == 404

    def test_sentiment_run_without_sentiment(self, client):
        response = client.get("/sentiment?run_id=1")
        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "none"
        assert "No sentiment data" in data.get("message", "")

    def test_sentiment_with_fast_mode_data(self, tmp_path, monkeypatch):
        from src.storage import TrackDatabase
        from src.analyzer import AnalyticsEngine
        from src.api import app, prompts as prompts_module

        test_db = TrackDatabase(db_path=str(tmp_path / "test.db"))
        run_id = test_db.create_run(config_hash="test")
        test_db.record_query(
            run_id=run_id,
            model_provider="ollama",
            model_name="gemma4:e2b",
            prompt="Best shoes?",
            response_text="Nike is great",
            mentions={"Nike": 1},
        )
        test_db.complete_run(
            run_id,
            metadata={
                "sentiment": {
                    "Nike": {
                        "prominence": 0.65,
                        "sentiment": 0.3,
                        "composite": 0.195,
                        "summary": "Positive",
                    }
                }
            },
        )

        monkeypatch.setattr(prompts_module, "_db", test_db)
        monkeypatch.setattr(prompts_module, "_engine", AnalyticsEngine(test_db))

        c = TestClient(app)
        resp = c.get(f"/sentiment?run_id={run_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "fast"
        assert "Nike" in data["brands"]
        assert data["brands"]["Nike"]["composite"] == 0.195

    def test_sentiment_latest(self, client):
        response = client.get("/sentiment-latest")
        assert response.status_code == 200
        data = response.json()
        assert "mode" in data


class TestUntestedEndpoints:
    def test_get_data_endpoint_brand(self, client):
        response = client.get("/data?brand=Nike&days=30")
        assert response.status_code == 200
        data = response.json()
        assert data["filters"]["brand"] == "Nike"
        assert "results" in data

    def test_post_run_start(self, client):
        response = client.post(
            "/run/start?enable_variations=true&num_variations=2&variation_strategy=semantic"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"

    def test_get_run_history(self, client):
        response = client.get("/run-history")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_trends(self, client):
        response = client.get("/trends?brand=Nike&days=30")
        assert response.status_code == 200
        data = response.json()
        assert "trend_data" in data or len(data) > 0

    def test_get_models(self, client):
        response = client.get("/models?brand=Nike&days=30")
        assert response.status_code == 200
        data = response.json()
        models = data["models"]
        assert isinstance(models, list)
        assert len(models) >= 0

    def test_get_export_default(self, client):
        response = client.get("/export")
        assert response.status_code == 200
        data = response.json()
        assert data["export_info"]["format"] == "json"
        assert isinstance(data["data"], list)

    def test_get_convergence_status(self, client):
        response = client.get("/convergence-status?run_id=1")
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == 1

    def test_get_convergence_status_not_found(self, client):
        response = client.get("/convergence-status?run_id=99999")
        assert response.status_code == 404

    def test_get_convergence_live(self, client):
        response = client.get("/convergence-live")
        assert response.status_code == 200
        data = response.json()
        assert "active" in data

    def test_get_visibility_by_segment(self, client):
        response = client.get("/visibility-by-segment?brand=Nike&dimension=intent&days=30")
        assert response.status_code == 200
        data = response.json()
        assert "segments" in data

    def test_get_segment_comparison(self, client):
        response = client.get("/segment-comparison?brands=Nike,Adidas&dimension=topic&days=30")
        assert response.status_code == 200
        data = response.json()
        assert "brands" in data

    def test_get_variation_drift(self, client):
        response = client.get("/variation-drift?canonical_id=1&brand=Nike&days=30")
        assert response.status_code == 200
        data = response.json()
        assert "variations" in data

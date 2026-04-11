"""Tests for API endpoints."""

import json
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
        data = response.json()


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

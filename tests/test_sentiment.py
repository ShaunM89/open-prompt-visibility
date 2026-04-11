"""Tests for sentiment analysis components."""

import json
from unittest.mock import MagicMock, patch

from src.analyzer import (
    MentionContext,
    MentionContextExtractor,
    SentimentAnalyzer,
    SentimentCIStrategy,
    SentimentHeuristics,
    SentimentResult,
)


BRANDS_CONFIG = {
    "Nike": {"keywords": ["Nike", "Swoosh"], "competitors": []},
    "Adidas": {"keywords": ["Adidas"], "competitors": []},
}


class TestMentionContextExtractor:
    def setup_method(self):
        self.extractor = MentionContextExtractor(BRANDS_CONFIG)

    def test_extract_single_mention(self):
        text = "I think Nike makes the best running shoes on the market today."
        contexts = self.extractor.extract(text, "Nike")
        assert len(contexts) >= 1
        assert contexts[0].brand == "Nike"
        assert "Nike" in contexts[0].snippet
        assert 0.0 <= contexts[0].position <= 1.0

    def test_extract_multiple_mentions(self):
        text = "Nike is great. Also Nike appears again later in the text."
        contexts = self.extractor.extract(text, "Nike")
        assert len(contexts) >= 2
        assert contexts[0].position < contexts[1].position

    def test_extract_no_mention(self):
        text = "Adidas makes great shoes."
        contexts = self.extractor.extract(text, "Nike")
        assert len(contexts) == 0

    def test_extract_empty_text(self):
        contexts = self.extractor.extract("", "Nike")
        assert len(contexts) == 0

    def test_position_labels(self):
        long_text = "Nike " + "word " * 100 + "Nike " + "word " * 100 + "Nike"
        contexts = self.extractor.extract(long_text, "Nike")
        labels = [c.position_label for c in contexts]
        assert labels[0] == "early"
        assert labels[-1] == "late"

    def test_position_label_middle(self):
        long_text = "word " * 50 + "Nike" + " word " * 50
        contexts = self.extractor.extract(long_text, "Nike")
        assert len(contexts) == 1
        assert contexts[0].position_label == "middle"

    def test_unknown_brand_returns_empty(self):
        contexts = self.extractor.extract("Some text", "UnknownBrand")
        assert len(contexts) == 0

    def test_snippet_has_ellipsis(self):
        long_text = "word " * 200 + "Nike" + " word " * 200
        contexts = self.extractor.extract(long_text, "Nike")
        assert len(contexts) >= 1
        assert "..." in contexts[0].snippet

    def test_uses_all_keywords(self):
        text = "The Swoosh brand is iconic."
        contexts = self.extractor.extract(text, "Nike")
        assert len(contexts) >= 1
        assert "Swoosh" in contexts[0].snippet


class TestSentimentHeuristics:
    def setup_method(self):
        self.heuristics = SentimentHeuristics()

    def test_positive_words(self):
        score = self.heuristics.score("Nike is the best and most excellent brand", "early")
        assert score > 0

    def test_negative_words(self):
        score = self.heuristics.score("Nike is terrible and disappointing", "early")
        assert score < 0

    def test_neutral_text(self):
        score = self.heuristics.score("Nike is mentioned here.", "middle")
        assert abs(score) < 0.5

    def test_position_early_boost(self):
        early = self.heuristics.score("Nike mentioned", "early")
        late = self.heuristics.score("Nike mentioned", "late")
        assert early >= late

    def test_crowded_brand_penalty(self):
        solo = self.heuristics.score("Nike is a great brand", "early", total_brands_in_context=1)
        crowded = self.heuristics.score("Nike is a great brand", "early", total_brands_in_context=5)
        assert solo > crowded

    def test_clamped_range(self):
        score = self.heuristics.score(
            "best excellent outstanding superior amazing wonderful perfect brilliant fantastic phenomenal",
            "early",
        )
        assert -1.0 <= score <= 1.0


class TestSentimentCIStrategy:
    def setup_method(self):
        self.strategy = SentimentCIStrategy()

    def test_returns_none_for_single_score(self):
        result = self.strategy.calculate(1, [0.5])
        assert result is None

    def test_returns_none_for_empty(self):
        result = self.strategy.calculate(0, [])
        assert result is None

    def test_ci_contains_mean(self):
        scores = [0.1, 0.3, 0.5, 0.7, 0.9]
        result = self.strategy.calculate(5, scores)
        assert result is not None
        mean = sum(scores) / len(scores)
        assert result[0] <= mean <= result[1]

    def test_ci_widens_with_variance(self):
        tight = self.strategy.calculate(5, [0.4, 0.5, 0.5, 0.5, 0.6])
        wide = self.strategy.calculate(5, [-0.8, 0.0, 0.5, 0.5, 0.9])
        assert tight is not None and wide is not None
        assert (tight[1] - tight[0]) < (wide[1] - wide[0])

    def test_ci_narrows_with_sample_size(self):
        import random

        random.seed(42)
        small = [random.gauss(0.3, 0.2) for _ in range(5)]
        large = [random.gauss(0.3, 0.2) for _ in range(20)]
        ci_small = self.strategy.calculate(5, small)
        ci_large = self.strategy.calculate(20, large)
        assert ci_small is not None and ci_large is not None
        assert (ci_small[1] - ci_small[0]) > (ci_large[1] - ci_large[0])

    def test_zero_variance(self):
        scores = [0.5, 0.5, 0.5, 0.5]
        result = self.strategy.calculate(4, scores)
        assert result is not None
        assert result[0] == result[1] == 0.5

    def test_large_sample_uses_normal_approx(self):
        scores = [0.1] * 50
        result = self.strategy.calculate(50, scores)
        assert result is not None
        assert result[0] == result[1] == 0.1

    def test_different_confidence_levels(self):
        scores = [0.1, 0.3, 0.5, 0.7, 0.9]
        ci90 = self.strategy.calculate(5, scores, confidence_level=90)
        ci99 = self.strategy.calculate(5, scores, confidence_level=99)
        assert ci90 is not None and ci99 is not None
        assert (ci90[1] - ci90[0]) < (ci99[1] - ci99[0])


class TestSentimentAnalyzer:
    def _make_config(self, mode="fast"):
        return {
            "analysis": {
                "provider": "ollama",
                "model": "gemma4:e2b",
                "temperature": 0.1,
            },
            "sentiment": {"mode": mode},
        }

    @patch("src.analyzer.create_adapter")
    def test_fast_mode_returns_result(self, mock_create):
        mock_adapter = MagicMock()
        mock_adapter.query.return_value = json.dumps(
            {
                "contexts": [{"prominence": 0.8, "sentiment": 0.5}],
                "aggregate": {
                    "prominence": 0.65,
                    "sentiment": 0.3,
                    "composite_score": 0.195,
                    "summary": "Brand is discussed positively",
                },
            }
        )
        mock_create.return_value = mock_adapter

        analyzer = SentimentAnalyzer(self._make_config("fast"))
        contexts = [
            MentionContext(
                brand="Nike",
                snippet="Nike is the best brand",
                position=0.1,
                mention_ordinal=1,
                position_label="early",
            )
        ]
        result = analyzer.analyze_fast("Nike", contexts)
        assert isinstance(result, SentimentResult)
        assert result.composite_score == 0.195
        assert result.prominence == 0.65
        assert result.sentiment == 0.3
        assert result.summary == "Brand is discussed positively"

    @patch("src.analyzer.create_adapter")
    def test_fast_mode_empty_contexts(self, mock_create):
        mock_create.return_value = MagicMock()
        analyzer = SentimentAnalyzer(self._make_config("fast"))
        result = analyzer.analyze_fast("Nike", [])
        assert result.composite_score == 0.0

    @patch("src.analyzer.create_adapter")
    def test_fast_mode_heuristic_fallback(self, mock_create):
        mock_adapter = MagicMock()
        mock_adapter.query.side_effect = RuntimeError("LLM down")
        mock_create.return_value = mock_adapter

        analyzer = SentimentAnalyzer(self._make_config("fast"))
        contexts = [
            MentionContext(
                brand="Nike",
                snippet="Nike is the best and excellent brand",
                position=0.1,
                mention_ordinal=1,
                position_label="early",
            )
        ]
        result = analyzer.analyze_fast("Nike", contexts)
        assert isinstance(result, SentimentResult)
        assert "Heuristic fallback" in (result.summary or "")

    @patch("src.analyzer.create_adapter")
    def test_detailed_mode_returns_result(self, mock_create):
        mock_adapter = MagicMock()
        mock_adapter.query.return_value = json.dumps(
            {
                "prominence": 0.8,
                "sentiment": 0.5,
                "composite_score": 0.4,
            }
        )
        mock_create.return_value = mock_adapter

        analyzer = SentimentAnalyzer(self._make_config("detailed"))
        result = analyzer.analyze_detailed("Nike", "Nike makes the best shoes")
        assert result.prominence == 0.8
        assert result.sentiment == 0.5
        assert result.composite_score == 0.4

    @patch("src.analyzer.create_adapter")
    def test_detailed_mode_empty_response(self, mock_create):
        mock_create.return_value = MagicMock()
        analyzer = SentimentAnalyzer(self._make_config("detailed"))
        result = analyzer.analyze_detailed("Nike", "")
        assert result.composite_score == 0.0

    @patch("src.analyzer.create_adapter")
    def test_detailed_mode_llm_failure(self, mock_create):
        mock_adapter = MagicMock()
        mock_adapter.query.side_effect = RuntimeError("LLM down")
        mock_create.return_value = mock_adapter

        analyzer = SentimentAnalyzer(self._make_config("detailed"))
        result = analyzer.analyze_detailed("Nike", "Nike shoes are great")
        assert result.prominence == 0.5
        assert result.composite_score == 0.0

    @patch("src.analyzer.create_adapter")
    def test_parse_llm_response_with_code_block(self, mock_create):
        mock_create.return_value = MagicMock()
        analyzer = SentimentAnalyzer(self._make_config())
        parsed = analyzer._parse_llm_response('```json\n{"prominence": 0.5}\n```')
        assert parsed["prominence"] == 0.5

    @patch("src.analyzer.create_adapter")
    def test_mode_set_from_config(self, mock_create):
        mock_create.return_value = MagicMock()
        analyzer = SentimentAnalyzer(self._make_config("detailed"))
        assert analyzer.mode == "detailed"


class TestStorageFormatBackwardCompat:
    def test_normalize_old_format(self):
        from src.storage import TrackDatabase

        db = TrackDatabase.__new__(TrackDatabase)
        result = db._normalize_mentions('{"Nike": 2, "Adidas": 1}')
        assert result["Nike"] == {"count": 2}
        assert result["Adidas"] == {"count": 1}

    def test_normalize_new_format(self):
        from src.storage import TrackDatabase

        db = TrackDatabase.__new__(TrackDatabase)
        data = {
            "Nike": {
                "count": 2,
                "sentiment": {"prominence": 0.65, "sentiment": 0.3, "composite": 0.195},
            }
        }
        result = db._normalize_mentions(json.dumps(data))
        assert result["Nike"]["count"] == 2
        assert result["Nike"]["sentiment"]["composite"] == 0.195

    def test_format_old_mentions_str(self):
        from src.storage import TrackDatabase

        db = TrackDatabase.__new__(TrackDatabase)
        result = db._format_mentions_str('{"Nike": 2, "Adidas": 1}')
        assert "Nike (2)" in result
        assert "Adidas (1)" in result

    def test_format_new_mentions_str(self):
        from src.storage import TrackDatabase

        db = TrackDatabase.__new__(TrackDatabase)
        data = {
            "Nike": {
                "count": 2,
                "sentiment": {"prominence": 0.65, "sentiment": 0.3, "composite": 0.195},
            }
        }
        result = db._format_mentions_str(json.dumps(data))
        assert "Nike (2" in result
        assert "composite:" in result

    def test_format_empty_mentions(self):
        from src.storage import TrackDatabase

        db = TrackDatabase.__new__(TrackDatabase)
        assert db._format_mentions_str("{}") == ""
        assert db._format_mentions_str(None) == ""

    def test_mixed_format(self):
        from src.storage import TrackDatabase

        db = TrackDatabase.__new__(TrackDatabase)
        data = {
            "Nike": {
                "count": 2,
                "sentiment": {"prominence": 0.65, "sentiment": 0.3, "composite": 0.195},
            },
            "Adidas": 1,
        }
        result = db._normalize_mentions(json.dumps(data))
        assert result["Nike"]["count"] == 2
        assert result["Adidas"] == {"count": 1}

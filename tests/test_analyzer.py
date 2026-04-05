"""Tests for mention detection."""

import pytest

from src.analyzer import MentionDetector


class TestMentionDetector:
    """Test keyword-based mention detection."""

    @pytest.fixture
    def mock_config(self):
        return {
            'brands': [
                {
                    'name': 'Nike',
                    'keywords': ['Nike', 'NIKE', 'Just Do It', 'Swoosh'],
                    'competitors': [
                        {'name': 'Adidas', 'keywords': ['Adidas', 'ADI']},
                        {'name': 'Reebok', 'keywords': ['Reebok']}
                    ]
                }
            ],
            'tracking': {'detection_method': 'keyword'}
        }

    def test_single_brand_mention(self, mock_config):
        detector = MentionDetector(mock_config)
        response = "I prefer Nike for running shoes."
        mentions = detector.detect(response)

        assert 'Nike' in mentions
        assert mentions['Nike'] >= 1

    def test_multiple_brand_mentions(self, mock_config):
        detector = MentionDetector(mock_config)
        response = "Nike vs Adidas: both are great brands."
        mentions = detector.detect(response)

        assert 'Nike' in mentions
        assert 'Adidas' in mentions

    def test_no_mentions(self, mock_config):
        detector = MentionDetector(mock_config)
        response = "The weather is nice today."
        mentions = detector.detect(response)

        assert mentions == {}

    def test_case_insensitive(self, mock_config):
        detector = MentionDetector(mock_config)
        response = "I bought NIKE shoes yesterday."
        mentions = detector.detect(response)

        assert 'Nike' in mentions

    def test_slogan_detection(self, mock_config):
        detector = MentionDetector(mock_config)
        response = "Just Do It - the best slogan ever."
        mentions = detector.detect(response)

        assert 'Nike' in mentions


class TestAnalyticsEngine:
    """Test analytics functions."""

    def test_variance_calculation_placeholder(self):
        """Placeholder for variance calculation tests."""
        # TODO: Implement with mock database
        pass

"""Tests for model adapters."""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.models import (
    OllamaAdapter,
    OpenAIAdapter,
    AnthropicAdapter,
    HuggingFaceAdapter,
    create_adapter,
)


class TestOllamaAdapter:
    """Test Ollama adapter."""

    @pytest.fixture
    def adapter(self):
        return OllamaAdapter(model="qwen3.5:122b", temperature=0.7)

    def test_init_default_endpoint(self, adapter):
        assert adapter.endpoint == "http://localhost:11434"
        assert adapter.provider == "ollama"

    @patch("src.models.requests.get")
    def test_health_check_success(self, mock_get, adapter):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": [{"name": "qwen3.5:122b"}]}
        mock_get.return_value = mock_response
        assert adapter.health_check() is True

    @patch("src.models.requests.get")
    def test_health_check_model_not_found(self, mock_get, adapter):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": [{"name": "llama2"}]}
        mock_get.return_value = mock_response
        assert adapter.health_check() is False

    @patch("src.models.requests.post")
    def test_query_success(self, mock_post, adapter):
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Test response"}
        mock_post.return_value = mock_response
        result = adapter.query("Test prompt")
        assert result == "Test response"
        mock_post.assert_called_once()


class TestOpenAIAdapter:
    """Test OpenAI adapter."""

    @pytest.fixture
    def adapter(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"}):
            return OpenAIAdapter(model="gpt-4o", temperature=0.7)

    def test_init(self, adapter):
        assert adapter.provider == "openai"
        assert adapter.model == "gpt-4o"

    @patch("src.models.requests.post")
    def test_query_success(self, mock_post, adapter):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "OpenAI response"}}]}
        mock_post.return_value = mock_response
        result = adapter.query("Test prompt")
        assert result == "OpenAI response"

    @patch("src.models.requests.get")
    def test_health_check_success(self, mock_get, adapter):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        assert adapter.health_check() is True

    @patch("src.models.requests.get")
    def test_health_check_failure(self, mock_get, adapter):
        mock_get.side_effect = Exception("Connection failed")
        assert adapter.health_check() is False


class TestAnthropicAdapter:
    """Test Anthropic adapter."""

    @pytest.fixture
    def adapter(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "ant-test-key"}):
            return AnthropicAdapter(model="claude-3-sonnet-20240229", temperature=0.7)

    def test_init(self, adapter):
        assert adapter.provider == "anthropic"
        assert adapter.model == "claude-3-sonnet-20240229"

    @patch("src.models.requests.post")
    def test_query_success(self, mock_post, adapter):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"content": [{"text": "Anthropic response"}]}
        mock_post.return_value = mock_response
        result = adapter.query("Test prompt")
        assert result == "Anthropic response"

    @patch("src.models.requests.post")
    def test_health_check(self, mock_post, adapter):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        assert adapter.health_check() is True


class TestHuggingFaceAdapter:
    """Test HuggingFace adapter."""

    @pytest.fixture
    def adapter(self):
        with patch.dict(os.environ, {"HUGGINGFACE_API_KEY": "hf-test-key"}):
            return HuggingFaceAdapter(model="meta-llama/Llama-2-7b", temperature=0.7)

    def test_init(self, adapter):
        assert adapter.provider == "huggingface"
        assert "meta-llama" in adapter.api_url

    @patch("src.models.requests.post")
    def test_query_success(self, mock_post, adapter):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = [{"generated_text": "HF response"}]
        mock_post.return_value = mock_response
        result = adapter.query("Test prompt")
        assert result == "HF response"

    @patch("src.models.requests.head")
    def test_health_check_success(self, mock_head, adapter):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_head.return_value = mock_response
        assert adapter.health_check() is True

    @patch("src.models.requests.head")
    def test_health_check_failure(self, mock_head, adapter):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_head.return_value = mock_response
        assert adapter.health_check() is False


class TestCreateAdapter:
    """Test adapter factory."""

    def test_create_ollama_adapter(self):
        adapter = create_adapter({"provider": "ollama", "model": "gemma4:e2b", "temperature": 0.7})
        assert isinstance(adapter, OllamaAdapter)
        assert adapter.model == "gemma4:e2b"

    def test_create_openai_adapter_fails_without_key(self):
        with pytest.raises(ValueError, match="API key not found"):
            create_adapter(
                {"provider": "openai", "model": "gpt-4o", "api_key_env": "NONEXISTENT_KEY"}
            )

    def test_create_anthropic_adapter_fails_without_key(self):
        with pytest.raises(ValueError, match="API key not found"):
            create_adapter(
                {
                    "provider": "anthropic",
                    "model": "claude-3-sonnet-20240229",
                    "api_key_env": "NONEXISTENT_KEY",
                }
            )

    def test_create_huggingface_adapter_fails_without_key(self):
        with pytest.raises(ValueError, match="API key not found"):
            create_adapter(
                {
                    "provider": "huggingface",
                    "model": "meta-llama/Llama-2-7b",
                    "api_key_env": "NONEXISTENT_KEY",
                }
            )

    def test_create_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            create_adapter({"provider": "unknown", "model": "test"})

    def test_create_ollama_with_endpoint(self):
        adapter = create_adapter(
            {"provider": "ollama", "model": "test", "endpoint": "http://custom:11434"}
        )
        assert adapter.endpoint == "http://custom:11434"

    def test_create_openai_with_key(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            adapter = create_adapter({"provider": "openai", "model": "gpt-4o"})
            assert isinstance(adapter, OpenAIAdapter)

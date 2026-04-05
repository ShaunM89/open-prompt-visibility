"""Tests for model adapters."""

from unittest.mock import MagicMock, patch

import pytest

from src.models import OllamaAdapter, create_adapter


class TestOllamaAdapter:
    """Test Ollama adapter."""

    @pytest.fixture
    def adapter(self):
        return OllamaAdapter(
            model='qwen3.5:122b',
            temperature=0.7
        )

    def test_init_default_endpoint(self, adapter):
        assert adapter.endpoint == 'http://localhost:11434'
        assert adapter.provider == 'ollama'

    @patch('src.models.requests.get')
    def test_health_check_success(self, mock_get, adapter):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'models': [{'name': 'qwen3.5:122b'}]
        }
        mock_get.return_value = mock_response

        assert adapter.health_check() == True

    @patch('src.models.requests.get')
    def test_health_check_model_not_found(self, mock_get, adapter):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'models': [{'name': 'llama2'}]
        }
        mock_get.return_value = mock_response

        assert adapter.health_check() == False

    @patch('src.models.requests.post')
    def test_query_success(self, mock_post, adapter):
        mock_response = MagicMock()
        mock_response.json.return_value = {'response': 'Test response'}
        mock_post.return_value = mock_response

        result = adapter.query('Test prompt')

        assert result == 'Test response'
        mock_post.assert_called_once()


class TestCreateAdapter:
    """Test adapter factory."""

    def test_create_ollama_adapter(self):
        config = {
            'provider': 'ollama',
            'model': 'qwen3.5:122b',
            'temperature': 0.7
        }
        adapter = create_adapter(config)

        assert isinstance(adapter, OllamaAdapter)
        assert adapter.model == 'qwen3.5:122b'

    def test_create_openai_adapter_fails_without_key(self):
        config = {
            'provider': 'openai',
            'model': 'gpt-4o',
            'api_key_env': 'NONEXISTENT_KEY'
        }

        with pytest.raises(ValueError, match='API key not found'):
            create_adapter(config)

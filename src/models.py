"""LLM Model Adapters for unified querying interface."""

import os
from abc import ABC, abstractmethod

import requests


class ModelAdapter(ABC):
    """Abstract base class for LLM model adapters."""

    def __init__(self, model: str, temperature: float = 0.7, **kwargs):
        self.model = model
        self.temperature = temperature
        self.kwargs = kwargs

    @abstractmethod
    def query(self, prompt: str) -> str:
        """Execute a query against the model and return response text."""
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Check if the model service is available."""
        pass

    @property
    @abstractmethod
    def provider(self) -> str:
        """Return the provider name (e.g., 'ollama', 'openai')."""
        pass

    def query_stream(self, prompt: str) -> str:
        """Execute query with streaming support. Falls back to non-streaming."""
        return self.query(prompt)


class OllamaAdapter(ModelAdapter):
    """Adapter for Ollama local LLM serving."""

    def __init__(self, model: str, temperature: float = 0.7, **kwargs):
        super().__init__(model, temperature, **kwargs)
        self.endpoint = kwargs.get('endpoint', os.getenv('OLLAMA_HOST', 'http://localhost:11434'))
        self.api_url = f"{self.endpoint}/api/generate"

    @property
    def provider(self) -> str:
        return "ollama"

    def query(self, prompt: str) -> str:
        """Query the Ollama model."""
        try:
            response = requests.post(
                self.api_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": self.temperature,
                    }
                },
                timeout=120
            )
            response.raise_for_status()
            result = response.json()
            return result.get('response', '')
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.endpoint}. "
                "Is Ollama running? (ollama serve)"
            )
        except requests.exceptions.Timeout:
            raise TimeoutError("Request to Ollama timed out after 120s")
        except Exception as e:
            raise RuntimeError(f"Ollama query failed: {e}")

    def health_check(self) -> bool:
        """Check if Ollama is running and model is available."""
        try:
            # Check if server is up
            tags_response = requests.get(
                f"{self.endpoint}/api/tags",
                timeout=5
            )
            tags_response.raise_for_status()
            available_models = [m['name'] for m in tags_response.json().get('models', [])]

            # Check if our model is available
            if self.model not in available_models:
                print(f"Warning: Model '{self.model}' not found in Ollama. Available: {available_models}")
                return False

            return True
        except requests.exceptions.ConnectionError:
            print(f"Cannot connect to Ollama at {self.endpoint}")
            return False
        except Exception as e:
            print(f"Ollama health check failed: {e}")
            return False


class OpenAIAdapter(ModelAdapter):
    """Adapter for OpenAI API."""

    def __init__(self, model: str, temperature: float = 0.7, **kwargs):
        super().__init__(model, temperature, **kwargs)
        self.api_key = self._get_api_key(kwargs)
        self.api_url = "https://api.openai.com/v1/chat/completions"
        # Convert model name from config format: gpt-4o -> gpt-4o
        self.model = model.replace("gpt-4o", "gpt-4o").replace("gpt-4", "gpt-4")

    def _get_api_key(self, kwargs: dict) -> str:
        """Get API key from env var specified in config."""
        env_var = kwargs.get('api_key_env', 'OPENAI_API_KEY')
        api_key = os.getenv(env_var)
        if not api_key:
            raise ValueError(f"API key not found. Set {env_var} environment variable.")
        return api_key

    @property
    def provider(self) -> str:
        return "openai"

    def query(self, prompt: str) -> str:
        """Query the OpenAI model."""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            response = requests.post(
                self.api_url,
                headers=headers,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": self.temperature,
                    "max_tokens": 2000
                },
                timeout=60
            )
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content']
        except requests.exceptions.HTTPError as e:
            error_body = e.response.text if e.response else 'No response body'
            raise RuntimeError(f"OpenAI API error ({e.response.status_code}): {error_body}")
        except Exception as e:
            raise RuntimeError(f"OpenAI query failed: {e}")

    def health_check(self) -> bool:
        """Check if OpenAI API is accessible."""
        try:
            response = requests.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            print(f"OpenAI health check failed: {e}")
            return False


class AnthropicAdapter(ModelAdapter):
    """Adapter for Anthropic Claude API."""

    def __init__(self, model: str, temperature: float = 0.7, **kwargs):
        super().__init__(model, temperature, **kwargs)
        self.api_key = self._get_api_key(kwargs)
        self.api_url = "https://api.anthropic.com/v1/messages"
        self.model = model  # e.g., "claude-3-sonnet-20240229"

    def _get_api_key(self, kwargs: dict) -> str:
        """Get API key from env var."""
        env_var = kwargs.get('api_key_env', 'ANTHROPIC_API_KEY')
        api_key = os.getenv(env_var)
        if not api_key:
            raise ValueError(f"API key not found. Set {env_var} environment variable.")
        return api_key

    @property
    def provider(self) -> str:
        return "anthropic"

    def query(self, prompt: str) -> str:
        """Query the Anthropic model."""
        try:
            headers = {
                "x-api-key": self.api_key,
                "content-type": "application/json",
                "anthropic-version": "2023-06-01"
            }
            response = requests.post(
                self.api_url,
                headers=headers,
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "system": "You are a helpful assistant.",
                    "temperature": self.temperature,
                    "max_tokens": 2000
                },
                timeout=60
            )
            response.raise_for_status()
            result = response.json()
            return result['content'][0]['text']
        except requests.exceptions.HTTPError as e:
            error_body = e.response.text if e.response else 'No response body'
            raise RuntimeError(f"Anthropic API error ({e.response.status_code}): {error_body}")
        except Exception as e:
            raise RuntimeError(f"Anthropic query failed: {e}")

    def health_check(self) -> bool:
        """Check if Anthropic API is accessible."""
        try:
            headers = {
                "x-api-key": self.api_key,
                "content-type": "application/json",
                "anthropic-version": "2023-06-01"
            }
            # Try a minimal request
            response = requests.post(
                self.api_url,
                headers=headers,
                json={
                    "model": "claude-3-sonnet-20240229",
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 1
                },
                timeout=10
            )
            return response.status_code in (200, 400)  # 400 means auth OK, invalid params
        except Exception as e:
            print(f"Anthropic health check failed: {e}")
            return False


class HuggingFaceAdapter(ModelAdapter):
    """Adapter for Hugging Face Inference API."""

    def __init__(self, model: str, temperature: float = 0.7, **kwargs):
        super().__init__(model, temperature, **kwargs)
        self.api_key = self._get_api_key(kwargs)
        self.api_url = f"https://api-inference.huggingface.co/models/{model}"

    def _get_api_key(self, kwargs: dict) -> str:
        """Get API key from env var."""
        env_var = kwargs.get('api_key_env', 'HUGGINGFACE_API_KEY')
        api_key = os.getenv(env_var)
        if not api_key:
            raise ValueError(f"API key not found. Set {env_var} environment variable.")
        return api_key

    @property
    def provider(self) -> str:
        return "huggingface"

    def query(self, prompt: str) -> str:
        """Query the Hugging Face model."""
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            response = requests.post(
                self.api_url,
                headers=headers,
                json={
                    "inputs": prompt,
                    "parameters": {
                        "temperature": self.temperature,
                        "max_new_tokens": 1000
                    }
                },
                timeout=120
            )
            response.raise_for_status()
            result = response.json()
            # HF returns different formats depending on model
            if isinstance(result, list) and len(result) > 0:
                return result[0].get('generated_text', '')
            return str(result)
        except Exception as e:
            raise RuntimeError(f"HuggingFace query failed: {e}")

    def health_check(self) -> bool:
        """Check if HF model is accessible."""
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            response = requests.head(self.api_url, headers=headers, timeout=10)
            return response.status_code < 500
        except Exception as e:
            print(f"HuggingFace health check failed: {e}")
            return False


def create_adapter(config: dict) -> ModelAdapter:
    """Factory function to create adapter from config."""
    provider = config['provider'].lower()

    adapters = {
        'ollama': OllamaAdapter,
        'openai': OpenAIAdapter,
        'anthropic': AnthropicAdapter,
        'huggingface': HuggingFaceAdapter,
    }

    if provider not in adapters:
        raise ValueError(f"Unknown provider: {provider}. Available: {list(adapters.keys())}")

    return adapters[provider](
        model=config['model'],
        temperature=config.get('temperature', 0.7),
        **{k: v for k, v in config.items() if k not in ['provider', 'model', 'temperature', 'enabled']}
    )

# Configuration Guide

## Quick Reference

### Change Query Model
Edit `configs/default.yaml`:
```yaml
models:
  - provider: "ollama"
    model: "nemotron-nano"  # Change to your preferred model
    enabled: true
```

### Change Query Count (for statistical significance)
```yaml
tracking:
  queries_per_prompt: 50  # Run each prompt 50 times
```

### Enable Multiple Models (parallel comparison)
```yaml
models:
  - provider: "ollama"
    model: "qwen3.5:122b"
    enabled: true
    description: "High quality"
    
  - provider: "ollama"
    model: "nemotron-nano"
    enabled: true
    description: "Fast iteration"
```

Both models will run independently, allowing you to compare results.

## Full Configuration Options

### Brand Configuration
```yaml
brands:
  - name: "Your Brand"
    keywords: ["keyword1", "keyword2"]  # Case-insensitive matching
    competitors:
      - name: "Competitor 1"
        keywords: ["comp1", "comp-1"]
```

### Model Configuration
| Field | Description | Default |
|-------|-------------|---------|
| `provider` | `ollama`, `openai`, `anthropic`, `huggingface` | Required |
| `model` | Model name | Required |
| `endpoint` | Ollama URL (for Ollama only) | `http://localhost:11434` |
| `enabled` | Enable/disable model | `true` |
| `temperature` | Generation temperature | `0.7` |
| `api_key_env` | Env var for API key (OpenAI/Anthropic) | Required for cloud APIs |

### Tracking Settings
| Field | Description | Default |
|-------|-------------|---------|
| `queries_per_prompt` | Repeat each prompt N times for variance | `10` |
| `max_retries` | Retry failed queries | `3` |
| `detection_method` | `keyword`, `llm`, or `both` | `both` |
| `llm_detection.model` | Model for LLM-based detection | `qwen2.5:7b` |

### Prompts
```yaml
prompts:
  category_name:
    - "Query 1"
    - "Query 2"
```

You can also merge prompts from files:
```yaml
prompts_from_files:
  - configs/prompts/brand.yaml
  - configs/prompts/topic.yaml
```

## Statistical Significance Guide

For meaningful statistical results:

| Queries/Prompt | Confidence Interval (@ 95%) | Use Case |
|----------------|----------------------------|----------|
| 10 | ±30% | Quick testing |
| 30 | ±17% | Development |
| 100 | ±10% | Production analysis |
| 500+ | ±4% | Research grade |

Example for production:
```yaml
tracking:
  queries_per_prompt: 100
```

## Using Fast Models (Nemotron-nano example)

For rapid iteration, use a smaller, faster model:

```yaml
models:
  - provider: "ollama"
    model: "nemotron-nano"  # Fast model (~1-2s/query)
    enabled: true
    description: "Fast iteration"
```

Recommended fast model settings:
```yaml
tracking:
  queries_per_prompt: 50    # More queries for same time
  temperature: 0.7
```

Production with quality:
```yaml
models:
  - provider: "ollama"
    model: "qwen3.5:122b"  # High quality (~15-30s/query)
    enabled: true
```

## Environment Variables

Copy `.env.example` to `.env`:
```bash
OPENAI_API_KEY=sk-...        # For OpenAI models
ANTHROPIC_API_KEY=...        # For Anthropic models
OLLAMA_HOST=http://localhost:11434  # Custom Ollama endpoint
```

## Export Configuration
```bash
# View current config
pvt config

# Export configuration as JSON
pvt config --json > config.json
```

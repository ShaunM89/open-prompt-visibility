# AI Visibility Tracker

Track how often AI chatbots mention your brand. Query multiple LLMs with test prompts, detect brand mentions in responses, and measure your visibility with statistical confidence.

## What It Does

When someone asks ChatGPT, Claude, or a local model "What are the best running shoes?", does your brand get mentioned? This tool answers that question systematically:

1. **Sends test prompts** to one or more LLMs (Ollama, OpenAI, Anthropic, HuggingFace)
2. **Detects brand mentions** using keyword matching and/or LLM-based analysis
3. **Calculates visibility scores** with Wilson confidence intervals
4. **Compares against competitors** to see where you stand
5. **Tracks trends over time** to see if visibility is improving

## Key Features

- **Multi-model support** -- query Ollama (local), OpenAI, Anthropic, and HuggingFace from one config
- **Statistical analysis** -- confidence intervals, variance analysis, anomaly detection
- **Sentiment detection** -- analyze how brands are portrayed (positive/neutral/negative) with decoupled analysis LLM
- **Adaptive sampling** -- automatically stop querying when confidence intervals narrow enough
- **Prompt variations** -- auto-generate prompt variations to reduce bias
- **Auto-prompt generation** -- generate brand-relevant prompts from domain context
- **CLI + Web Dashboard** -- command-line interface and Next.js dashboard
- **SQLite storage** -- all results stored locally, exportable to CSV/JSON

## Prerequisites

- **Python 3.9+** -- [python.org/downloads](https://www.python.org/downloads/)
- **Ollama** (recommended) -- [ollama.com/download](https://ollama.com/download)
- **Node.js 18+** (optional, for the web dashboard) -- [nodejs.org](https://nodejs.org/)

## Quick Start

### 1. Install

```bash
git clone https://github.com/ShaunM89/open-prompt-visibility.git
cd open-prompt-visibility
pip install -e .
```

### 2. Set up Ollama

```bash
# Install Ollama from https://ollama.com/download, then:
ollama pull gemma4:e2b
```

### 3. Configure your brands

Edit `configs/users/brands.yaml` with your brand and competitors:

```yaml
brands:
  - name: "YourBrand"
    keywords: ["YourBrand", "your brand"]
    competitors:
      - name: "Competitor1"
        keywords: ["Competitor1"]
      - name: "Competitor2"
        keywords: ["Competitor2"]
```

Edit `configs/users/prompts.yaml` with prompts relevant to your industry:

```yaml
prompts:
  - "What are the best products in [your industry]?"
  - "Compare the top brands for [your use case]"
```

### 4. Run tracking

```bash
pvt run --config configs/default.yaml
```

### 5. View results

```bash
# View brand trends with confidence intervals
pvt trends "YourBrand" --days 30 --ci 95

# View database statistics
pvt stats

# Export results
pvt export --format csv --output results.csv
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `pvt run` | Run a tracking batch across all configured models |
| `pvt run --model-only ollama:gemma4:e2b` | Run with only the specified model |
| `pvt run --model ollama:gemma4:e2b` | Add a model alongside configured models |
| `pvt run --enable-variations` | Run with auto-generated prompt variations |
| `pvt run --enable-auto-gen` | Run with auto-generated brand prompts |
| `pvt run --sentiment-mode fast` | Run with post-batch sentiment analysis |
| `pvt run --sentiment-mode detailed` | Run with per-query sentiment analysis |
| `pvt run --analysis-model ollama:gemma4:e2b` | Override the analysis LLM |
| `pvt run --target-ci-width 15` | Set adaptive sampling CI target |
| `pvt stats` | Show database statistics |
| `pvt trends "Brand"` | Show mention trends with confidence intervals |
| `pvt export -f csv -o out.csv` | Export results to CSV or JSON |
| `pvt config` | Display the active configuration |
| `pvt serve` | Start the API server (for the web dashboard) |

## Web Dashboard

The project includes a Next.js dashboard for visual analysis.

### Setup

```bash
# Terminal 1: Start the API server
pvt serve

# Terminal 2: Start the dashboard
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to view the dashboard.

The dashboard provides:
- Visibility score with confidence intervals
- Competitor comparison charts
- Paginated prompt results with filtering
- Run history with success rates
- Statistical summary with anomaly detection
- Sentiment analysis with color-coded brand cards

## Configuration

The tool uses YAML configuration files in `configs/`:

- `configs/default.yaml` -- main config entry point
- `configs/tool/config.yaml` -- model settings, tracking parameters, detection method
- `configs/users/brands.yaml` -- your brands and competitors
- `configs/users/prompts.yaml` -- test prompts

See [CONFIG.md](CONFIG.md) for the full configuration reference.

### Environment Variables

For cloud LLM providers, set API keys in a `.env` file (see `.env.example`):

```bash
OPENAI_API_KEY=sk-your-key
ANTHROPIC_API_KEY=your-key
OLLAMA_HOST=http://localhost:11434  # optional, defaults to localhost
```

## How It Works

```
configs/ --> VisibilityTracker --> ModelAdapters (Ollama/OpenAI/Anthropic/HF)
                  |                        |
                  v                        v
           PromptGenerator          LLM Responses
                  |                        |
                  v                        v
           MentionDetector -----> TrackDatabase (SQLite)
                                          |
                                          v
                                   AnalyticsEngine --> CLI / API / Dashboard
```

1. **VisibilityTracker** loads config and orchestrates the tracking run
2. **PromptGenerator** creates prompt variations and auto-generates prompts
3. **ModelAdapters** send prompts to configured LLMs
4. **MentionDetector** scans responses for brand mentions (keyword + LLM hybrid)
5. **SentimentAnalyzer** assesses how brands are portrayed using a separate analysis LLM
6. **AdaptiveSampler** stops querying when confidence intervals converge
7. **TrackDatabase** stores all results in SQLite
8. **AnalyticsEngine** calculates statistics, confidence intervals, and anomalies
9. Results are surfaced via CLI commands, FastAPI endpoints, or the Next.js dashboard

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and contribution guidelines.

## License

MIT -- see [LICENSE](LICENSE) for details.

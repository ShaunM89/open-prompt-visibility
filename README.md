# AI Visibility Tracker
A comprehensive dashboard for monitoring LLM brand visibility in responses across multiple models and providers.

![Version](https://img.shields.io/badge/version-0.1.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-development-brightgreen)

## ✨ Features

- **Visibility Score**: Calculate how often your target brand is mentioned across diverse prompts
- **Competitor Analysis**: Compare mention rates vs. competitors (Adidas, Mistral, etc.)
- **Model Comparison**: Track performance across different LLMs (Nemotron, Qwen, Llama, etc.)
- **Statistical Analysis**: Confidence intervals, sample adequacy, statistical significance
- **Prompt Management**: Track prompts used and results in structured database
- **Auto-Prompt Generation**: Generate relevant prompts from brand domains
- **Query Fan-Out**: Statistical robustness through multiple attempts

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- Ollama (for local LLMs)
- Node.js 20+ (for frontend)

### Setup

```bash
# Install dependencies
pip install -r requirements.txt
cd frontend && npm install

# Configure
cp .env.example .env
# Edit .env with your API keys (or set to empty for mock)

# Run
python main.py
cd ../frontend && npm run dev
```

Visit: http://localhost:3000

## 📊 Dashboard Components

- **VisibilityScoreCard**: Overall score with trend and breakdown
- **QuickStats**: Key metrics (mentions, models, queries)
- **CompetitorComparisonChart**: Brand vs. competitor analysis
- **PromptTable**: Detailed prompt results with pagination
- **RunHistoryPanel**: Monitoring of analysis runs

## 🛠️ Tech Stack

**Backend:**
- Python 3.12
- FastAPI
- SQLite/PostgreSQL
- FastLLM for model management

**Frontend:**
- Next.js 14
- TypeScript
- Tailwind CSS
- Recharts for visualizations

## 📝 Configuration

See `CONFIG.md` and `configs/` directory for:
- API key settings
- Brand definitions
- Prompt tracking settings
- Model configuration

## 🧪 Testing

```bash
# Run API tests
python -m pytest tests/

# Test API endpoints
python test_api.py
```

## 📂 Project Structure

```
├── frontend/          # Next.js dashboard
├── src/              # Python backend
│   ├── analyzer.py   # Statistical analysis
│   ├── tracker.py    # Batch prompting
│   ├── storage.py    # Database access
│   └── api/          # Endpoint modules
├── configs/          # Configuration files
├── tests/            # Test suite
└── README.md         # This file
```

## 🔗 API Endpoints

| Endpoint | Description |
|------ - ---|
| `/api/data` | Get brand data |
| `/api/statistical-summary` | Statistical metrics |
| `/api/competitors` | Competitor analysis |
| `/api/prompts` | Prompts list |
| `/api/run-history` | Run history |

## 📚 Documentation

- [Enhancement Plan](ENHANCEMENT_PLAN.md) - Future improvements
- [Implementation Brief](IMPLEMENTATION_BRIEF.md) - Current scope
- [Configuration Guide](CONFIG.md) - Setup instructions

## 🤝 Contributing

Pull requests welcome! Please read the code and submit issues for bugs.

## 📄 License

MIT License - See [LICENSE](LICENSE) file for details.

## 💬 Support

For issues, please create a GitHub issue. For questions, open a discussion.

---

**Built with ❤️ for AI transparency and visibility tracking**

# Contributing to AI Visibility Tracker

## Development Setup

### Backend (Python)

```bash
git clone https://github.com/ShaunM89/open-prompt-visibility.git
cd open-prompt-visibility
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Frontend (Next.js)

```bash
cd frontend
npm install
```

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run a specific test file
pytest tests/test_analyzer.py
```

## Code Style

- Python: formatted with `ruff` (line length 100)
- TypeScript: formatted with the project's ESLint config

```bash
# Lint Python code
ruff check src/ main.py

# Format Python code
ruff format src/ main.py
```

## Project Structure

```
main.py                  # CLI entry point (click commands)
src/
  tracker.py             # Core tracking orchestrator
  models.py              # LLM model adapters (Ollama, OpenAI, etc.)
  analyzer.py            # Mention detection + statistical analysis
  storage.py             # SQLite database layer
  prompt_generator.py    # Prompt variations + auto-generation
  api/
    __init__.py           # FastAPI app
    prompts.py            # API endpoints
frontend/                # Next.js dashboard
configs/                 # YAML configuration files
tests/                   # pytest test suite
```

## Making Changes

1. Create a branch: `git checkout -b your-feature`
2. Make your changes
3. Run tests: `pytest`
4. Submit a pull request

## Reporting Issues

Open an issue on GitHub with:
- What you expected to happen
- What actually happened
- Steps to reproduce
- Your Python version and OS

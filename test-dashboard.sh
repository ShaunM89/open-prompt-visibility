#!/bin/bash
# test-dashboard.sh - Test script for Prompt Visibility Dashboard

# Usage instructions for: prompt-visibility-tracking/frontend
# =======================================================

echo "=============================================="
echo "  Prompt Visibility Dashboard - Usage Guide   "
echo "=============================================="
echo ""
echo "This tool analyzes AI model performance metrics."
echo ""
echo "Quick Start:"
echo ""
echo "  1. Build the frontend:"
echo "     cd frontend && npm run build"
echo ""
echo "  2. Start the API server:"
echo "     cd .. && python backend.py --port 8000"
echo ""
echo "  3. Start the frontend:"
echo "     cd frontend && npm run dev"
echo ""
echo "  4. Open browser: http://localhost:3000"
echo ""
echo "=============================================="
echo ""

# Show available dashboards
echo "Available Dashboard Paths:"
echo "  - / (default: all brands)"
echo "  - /qwen (Qwen model)"
echo "  - /mistral"
echo "  - /gemini"
echo "  - /openai"
echo "  - /anthropic"
echo "  - /nvidia"
echo ""

# Environment variables
echo "Environment Variables:"
echo "  API_BASE_URL  - Base URL for API (default: http://localhost:8000)"
echo "  OPENAI_KEY    - OpenAI API key"
echo "  AZURE_KEY     - Azure API key"
echo "  MODEL_NAMES   - Comma-separated list of models to analyze"
echo ""

echo "=============================================="
echo "  Sample Metrics to Analyze:"
echo "=============================================="
echo "  - Mention Rate  : How often models are mentioned in context"
echo "  - Share of Voice: Model's share of total mentions (vs competitors)"
echo "  - Statistical Summary: Mean, sample size, coefficient of variation"
echo ""

echo "=============================================="
echo "  Technical Details:"
echo "=============================================="
echo "  Stack: Next.js 14, TypeScript, Tailwind CSS, Recharts"
echo "  API: FastAPI backend with FastLLM integration"
echo "  Models: Nemotron-4, Qwen2.5, Llama3, Gemini, Mistral, etc."
echo ""

# Check if files exist
FILES_OK=true

if [ ! -f "frontend/src/app/components/VisibilityScoreCard.tsx" ]; then
    echo "❌ Missing: VisibilityScoreCard.tsx"
    FILES_OK=false
fi

if [ ! -f "frontend/src/app/components/dashboard.tsx" ]; then
    echo "❌ Missing: dashboard.tsx"
    FILES_OK=false
fi

if [ ! -d "frontend/out" ]; then
    echo "⚠️  Not built yet. Run: npm run build"
fi

echo ""
if [ "$FILES_OK" = true ]; then
    echo "✅ All required files present"
else
    echo "❌ Some files missing"
fi
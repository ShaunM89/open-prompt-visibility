#!/bin/bash
# AI Visibility Tracker - Dashboard Launch Script
# Usage: ./start_dashboard.sh [PORT]
# Default port: 3002

set -e

# Configuration
FRONTEND_DIR="$(dirname "$0")/frontend"
PORT=${1:-3002}
DB_PATH="$(dirname "$0")/data/tracks.db"

echo "======================================"
echo "AI Visibility Tracker Dashboard"
echo "======================================"
echo ""

# Step 1: Kill any existing Next.js processes
echo "[1/5] Stopping any running dashboard instances..."
pkill -9 -f "next start" 2>/dev/null || true
pkill -9 -f "next dev" 2>/dev/null || true
sleep 1

# Step 2: Check database exists
echo "[2/5] Checking database..."
if [ ! -f "$DB_PATH" ]; then
    echo "ERROR: Database not found at $DB_PATH"
    echo ""
    echo "Run 'pvt run' first to collect data:"
    echo "  source .venv/bin/activate"
    echo "  pvt run"
    exit 1
fi
echo "  Database found: $DB_PATH"

# Step 3: Clean build cache
echo "[3/5] Cleaning build cache..."
cd "$FRONTEND_DIR"
rm -rf .next .turbo node_modules/.cache 2>/dev/null || true
echo "  Build cache cleared"

# Step 4: Rebuild frontend
echo "[4/5] Rebuilding frontend..."
npm run build > /tmp/dashboard-build.log 2>&1
if [ $? -ne 0 ]; then
    echo "ERROR: Build failed. See /tmp/dashboard-build.log"
    tail -20 /tmp/dashboard-build.log
    exit 1
fi
echo "  Build successful"

# Step 5: Start server
echo "[5/5] Starting dashboard server..."
echo ""
echo "======================================"
echo "Dashboard URL: http://localhost:$PORT"
echo "API Endpoint:  http://localhost:$PORT/api/data"
echo "Database:      $DB_PATH"
echo ""
echo "Press Ctrl+C to stop"
echo "======================================"
echo ""

PORT=$PORT ./node_modules/.bin/next start

#!/bin/bash
# Launch the Next.js dashboard on port 3001

cd "$(dirname "$0")/frontend"
export PORT=3001

echo "Starting dashboard at http://localhost:3001"
npm run start

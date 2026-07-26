#!/bin/bash

echo "⚔️  SOLO LEVELING FITNESS SYSTEM ⚔️"
echo "===================================="
echo ""
echo "Starting the Hunter Training System..."
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install/update requirements
echo "Installing dependencies..."
pip install -r requirements.txt --quiet

echo ""
echo "✅ Server starting..."
echo ""
echo "Access the application at: http://localhost:5000"
echo ""
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "ℹ️  Tip: The 'Become Like...' AI physique analyzer needs an API key."
    echo "   export ANTHROPIC_API_KEY=\"your-key-here\"  (get one at console.anthropic.com)"
    echo ""
fi
echo "Press Ctrl+C to stop the server"
echo ""

# Start the Flask server
cd backend
python app.py

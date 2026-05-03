#!/bin/bash

# Activate virtual environment if needed
if [ -d "venv" ]; then
    source venv/bin/activate
fi

echo "Generating data map..."
python3 build_ui_data.py

echo ""
echo "=========================================================="
echo "Starting local server at http://localhost:8000/ui/"
echo "Press Ctrl+C to stop the server"
echo "=========================================================="

python3 -m http.server 8000

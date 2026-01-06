#!/bin/bash
# Vehicle Data Generator - Unix/Mac runner
# Usage: ./run.sh [mode] [options]

cd "$(dirname "$0")"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Python3 is not installed!"
    echo "Please install Python from https://python.org"
    exit 1
fi

# Check if venv exists, if not create it
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate venv
source .venv/bin/activate

# Install dependencies if needed
if ! pip show python-dotenv &> /dev/null; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

# Check for .env file
if [ ! -f ".env" ]; then
    echo ""
    echo "========================================"
    echo "WARNING: .env file not found!"
    echo "========================================"
    echo ""
    echo "Please create a .env file with your OpenRouter API key."
    echo "You can copy .env.example and add your key:"
    echo "  cp .env.example .env"
    echo ""
    exit 1
fi

# Run the generator with any arguments passed
echo ""
echo "Starting Vehicle Data Generator..."
echo ""
python generate_vehicles.py "$@"

#!/bin/bash
echo "Starting EquiScope FastAPI backend dev server..."
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

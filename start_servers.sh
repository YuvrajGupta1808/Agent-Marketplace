#!/bin/bash
# Print the exact commands needed to start the seller, API, and Streamlit apps.

echo "🚀 Starting Agent Marketplace Servers"
echo "======================================"
echo ""
echo "Creating data directory..."
mkdir -p data
CERT_FILE="$(./venv312/bin/python -m certifi 2>/dev/null)"

echo ""
echo "Terminal 1: Starting Seller Agent Server (port 8001)..."
echo "Run this in a new terminal:"
echo "  SSL_CERT_FILE=\"$CERT_FILE\" ./venv312/bin/python -m uvicorn seller_agent.server:app --port 8001 --reload"
echo ""

echo "Terminal 2: Starting API Server (port 8000)..."
echo "Run this in a new terminal:"
echo "  SSL_CERT_FILE=\"$CERT_FILE\" ./venv312/bin/python -m uvicorn api.server:app --port 8000 --reload"
echo ""

echo "Terminal 3: Starting Streamlit UI (port 8501)..."
echo "Run this in a new terminal:"
echo "  SSL_CERT_FILE=\"$CERT_FILE\" ./venv312/bin/streamlit run app.py --server.port 8501"
echo ""

echo "To test once both servers are running:"
echo "  ./venv312/bin/python demo/run_demo.py"
echo ""
echo "Or to run a single query test:"
echo "  ./venv312/bin/python -c \"from test_embedded import test_embedded_flow; test_embedded_flow()\""

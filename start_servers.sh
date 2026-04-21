#!/bin/bash
# Start both the seller and API servers

echo "🚀 Starting Agent Marketplace Servers"
echo "======================================"
echo ""
echo "Creating data directory..."
mkdir -p data

echo ""
echo "Terminal 1: Starting Seller Agent Server (port 8001)..."
echo "Run this in a new terminal:"
echo "  uvicorn seller_agent.server:app --port 8001 --reload"
echo ""

echo "Terminal 2: Starting API Server (port 8000)..."
echo "Run this in a new terminal:"
echo "  uvicorn api.server:app --port 8000 --reload"
echo ""

echo "To test once both servers are running:"
echo "  python demo/run_demo.py"
echo ""
echo "Or to run a single query test:"
echo "  python -c \"from test_embedded import test_embedded_flow; test_embedded_flow()\""

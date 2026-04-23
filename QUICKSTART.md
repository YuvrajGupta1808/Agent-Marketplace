# Agent Marketplace Quick Start

## ✅ You're All Set!

Your `.env` file is configured with Circle credentials and Featherless API key.

---

## Option 1: Embedded Testing (Fastest - No External Services)

**Run instantly without any servers:**

```bash
python test_embedded.py
```

This creates agents, runs the marketplace, and shows payments - all in ~3 seconds. Perfect for:
- Quick feature testing
- Development iteration
- CI/CD pipelines

---

## Option 2: Real Servers (Full Integration)

**Start in 2 Terminal Windows:**

### Terminal 1: Seller Agent Server
```bash
mkdir -p data
SSL_CERT_FILE="$(./venv312/bin/python -m certifi)" ./venv312/bin/python -m uvicorn seller_agent.server:app --port 8001 --reload
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8001
```

### Terminal 2: API Server
```bash
SSL_CERT_FILE="$(./venv312/bin/python -m certifi)" ./venv312/bin/python -m uvicorn api.server:app --port 8000 --reload
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### Terminal 3: Streamlit Demo UI
```bash
SSL_CERT_FILE="$(./venv312/bin/python -m certifi)" ./venv312/bin/streamlit run app.py --server.port 8501
```

### Terminal 4: Run a Query
```bash
# Test single query
./venv312/bin/python -c "
import httpx
client = httpx.Client(timeout=30)

# Create user
user = client.post('http://localhost:8000/users', json={'display_name': 'Test User'}).json()['user']
print(f'User: {user[\"id\"]}')

# Create buyer
buyer = client.post('http://localhost:8000/agents', 
    json={'user_id': user['id'], 'role': 'buyer', 'name': 'Buyer'}).json()['agent']
print(f'Buyer: {buyer[\"id\"]}')

# Create seller
seller = client.post('http://localhost:8000/agents',
    json={'user_id': user['id'], 'role': 'seller', 'name': 'Seller'}).json()['agent']
print(f'Seller: {seller[\"id\"]}')

# Run marketplace
result = client.post('http://localhost:8000/run', json={
    'user_goal': 'What is Arc?',
    'buyer_agent_id': buyer['id'],
    'seller_agent_id': seller['id'],
    'thread_id': 'test-1'
}).json()

print(f'\\nFinal Answer (first 200 chars):\\n{result[\"final_answer\"][:200]}...')
print(f'\\nPayments: {len(result[\"payments\"])} transaction(s)')
for p in result['payments']:
    print(f'  - Task {p[\"task_id\"]}: {p[\"amount_usdc\"]} USDC - State: {p[\"state\"]}')
"
```

Or run the full demo (55 queries):
```bash
python demo/run_demo.py
```

---

## What's Configured

### Circle Wallet Integration
- ✅ CIRCLE_API_KEY: Set
- ✅ CIRCLE_ENTITY_SECRET: Set
- ✅ Will automatically create wallets for buyer and seller
- ✅ `SSL_CERT_FILE` can be sourced from `certifi` for Circle TLS verification

### LLM Integration
- ✅ FEATHERLESS_API_KEY: Set
- ✅ Models: Llama-3.3-70B (planner) + Llama-3.1-8B (seller)
- ✅ Mode: Heuristic planning with stub research

### Arc Testnet
- ✅ Chain ID: 5042002
- ✅ RPC: https://rpc.testnet.arc.network
- ✅ Explorer: https://testnet.arcscan.app
- ✅ USDC Contract: 0x3600...

---

## Status

| Component | Status | Details |
|-----------|--------|---------|
| Embedded Mode | ✅ Working | No setup needed |
| Circle Wallets | ✅ Required | Real Circle wallets only |
| Circle Payments | ✅ Required | Real Circle payment flow only |
| Circle API | ✅ Required | Install if needed: `pip install circle-developer-controlled-wallets` |
| Database | ✅ Ready | SQLite at `data/marketplace.db` |

---

## Troubleshooting

**Issue: "Connection refused" when running servers**
- Check that ports 8000 and 8001 are available
- Kill any existing processes: `lsof -i :8000` and `lsof -i :8001`

**Issue: "Circle wallet provisioning failed"**
- Ensure `CIRCLE_API_KEY` and `CIRCLE_ENTITY_SECRET` are set
- Start the process with `SSL_CERT_FILE="$(./venv312/bin/python -m certifi)"` if your macOS trust store is not being picked up

**Issue: Tests hang**
- Ctrl+C to stop
- Check that seller server is running (if using server mode)

---

## Next Steps

1. **Try embedded test**: `python test_embedded.py`
2. **Start real servers**: Use Terminal 1 & 2 above
3. **Check Circle wallets**: `curl http://localhost:8000/health`
4. **Run full demo**: `python demo/run_demo.py`
5. **View on Arc Explorer**: Paste tx hash from output into https://testnet.arcscan.app

---

**Questions?** Check PLAN.md for architecture details.

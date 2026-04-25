# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

Agent Marketplace is an agentic AI system for autonomous commerce on the Arc Testnet. It coordinates buyer and seller agents to negotiate, transact, and exchange value through blockchain-based nano-payments. The system visualizes agent interactions, tracks micro-transactions in real-time, and integrates Circle Programmable Wallets for on-chain settlement.

**Key Innovation**: Multi-agent orchestration with LangGraph, combined with Circle wallet integration for sub-cent USDC payments on Arc Testnet.

## Architecture

### High-Level Flow

```
User Goal
  ↓
[Orchestrator] - LangGraph coordination layer
  ├→ plan_tasks: Decompose user goal into researchable tasks
  ├→ ask_clarification: Request user input if goal is ambiguous
  └→ buyer_agent_node: Execute buyer agent for each task
       ├→ discover_seller: Find available seller agents
       ├→ plan_research_steps: Plan how to research
       ├→ execute_payment: Make Circle nano-payment
       ├→ send_research_request: Request seller to research
       └→ fetch_result: Collect seller's result
  └→ synthesize_answer: Aggregate results and return to user
```

### Core Components

**1. Orchestrator (`orchestrator/`)**
- Coordinates workflow across buyer agents and sellers
- State: list of tasks, results, payments, failed tasks, clarification needed
- Nodes: plan_tasks, ask_clarification, buyer_agent_node, synthesize_answer
- Graph: LangGraph StateGraph with in-memory checkpointing

**2. Buyer Agent (`buyer_agent/`)**
- Executes individual tasks by discovering sellers, planning, paying, and fetching results
- State: task_id, query, execution_plan, buyer_agent_id, seller_agent_id, wallet details
- Nodes:
  - `discover_seller`: Find seller endpoint via registry or hardcoded mapping
  - `plan_research_steps`: Create execution steps using LLM
  - `execute_payment`: Use Circle SDK to send USDC nano-payment
  - `send_research_request`: HTTP POST task to seller agent
  - `fetch_result`: Poll/fetch result from seller agent
- Returns: ResearchResult with title, summary, bullets, citations, tx_hash, Circle transaction ID

**3. Seller Agent (`seller_agent/`)**
- FastAPI endpoint that processes research requests
- Nodes:
  - `retriever`: Fetch web context (stubbed in current implementation)
  - `researcher`: LLM-based research using Featherless API (or stub research)
  - Returns: JSON with summary and bullet points

**4. API Server (`api/server.py`)**
- FastAPI REST endpoints for users, agents, wallet provisioning
- Coordinates orchestrator execution
- Endpoints:
  - `/users`: Create, list, get users
  - `/agents`: Create, list agents (auto-provisions Circle wallets)
  - `/run`: Execute orchestrator for user goal
  - `/health`: System health check
- Handles Circle SDK errors with graceful fallbacks

**5. Database (`shared/database.py`, `shared/repository.py`)**
- SQLite at `data/marketplace.db`
- Tables: users, agents, wallets, app_config
- MarketplaceRepository class provides ORM-like access
- Auto-initializes on app startup

**6. Wallet Integration (`shared/circle_client.py`, `shared/provisioning.py`)**
- Circle Programmable Wallets (developer-controlled)
- Wallet set created once, reused across wallets
- Auto-generates ARC-TESTNET addresses (42-char hex)
- Stores wallet metadata in SQLite with encryption

**7. Frontend (`ui/` - Next.js, `app.py` - Streamlit)**
- Next.js UI: React, TypeScript, Tailwind CSS, React Flow for agent graph visualization
- Streamlit UI: Legacy Python web interface
- Both consume `/run` endpoint for orchestration

### Key Dependencies

- **LangGraph**: Agent orchestration and state graphs
- **FastAPI**: REST API server
- **Circle SDK**: Blockchain wallet management and payments
- **OpenAI SDK**: LLM inference (configured to use Featherless API endpoint)
- **Pydantic**: Type validation and serialization
- **SQLite3**: Persistence layer

## Development Workflow

### Environment Setup

```bash
# Python environment (venv312)
./venv312/bin/python --version  # Should be 3.12+

# .env file required with:
# - CIRCLE_API_KEY
# - CIRCLE_ENTITY_SECRET
# - FEATHERLESS_API_KEY
# - DATABASE_FILE (defaults to data/marketplace.db)
```

### Running Servers

**Option 1: Embedded Test (Fastest)**
```bash
python test_embedded.py
```
Creates agents and runs marketplace flow entirely in-process, no external servers needed.

**Option 2: Real Servers**

Terminal 1 - Seller Agent Server (port 8001):
```bash
SSL_CERT_FILE="$(./venv312/bin/python -m certifi)" ./venv312/bin/python -m uvicorn seller_agent.server:app --port 8001 --reload
```

Terminal 2 - API Server (port 8000):
```bash
SSL_CERT_FILE="$(./venv312/bin/python -m uvicorn api.server:app --port 8000 --reload
```

Terminal 3 - Streamlit UI (port 8501, optional):
```bash
SSL_CERT_FILE="$(./venv312/bin/python -m certifi)" ./venv312/bin/streamlit run app.py --server.port 8501
```

Terminal 4 - Next.js Frontend (port 3000, optional):
```bash
npm run dev
```

**Or use the helper script:**
```bash
./start_servers.sh
```

### Frontend Development

```bash
npm install          # Install dependencies
npm run dev          # Start dev server (port 3000)
npm run build        # Build for production
npm run lint         # Run ESLint
```

The frontend expects the API at `http://localhost:8000` and Seller Agent at `http://localhost:8001`.

### Testing

**Quick Test (Recommended)**
```bash
python test_embedded.py
```

**Full Integration Test**
```bash
python test_with_circle.py
```

**Demo (55 queries)**
```bash
python demo/run_demo.py
```

**Single Query via HTTP**
```bash
python -c "
import httpx
client = httpx.Client(timeout=30)
user = client.post('http://localhost:8000/users', json={'display_name': 'Test User'}).json()['user']
buyer = client.post('http://localhost:8000/agents', json={'user_id': user['id'], 'role': 'buyer', 'name': 'Buyer'}).json()['agent']
seller = client.post('http://localhost:8000/agents', json={'user_id': user['id'], 'role': 'seller', 'name': 'Seller'}).json()['agent']
result = client.post('http://localhost:8000/run', json={'user_goal': 'What is Arc?', 'buyer_agent_id': buyer['id'], 'seller_agent_id': seller['id'], 'thread_id': 'test-1'}).json()
print(result['final_answer'][:200])
"
```

## Database Schema

SQLite tables created automatically at startup:

| Table | Purpose |
|-------|---------|
| `app_config` | Application-wide settings (key-value store) |
| `users` | User accounts (owner of agents) |
| `wallets` | Circle wallets with blockchain addresses |
| `agents` | Buyer/seller agents linked to users and wallets |

**Location**: `data/marketplace.db` (configurable via `DATABASE_FILE` env var)

**Foreign Keys**: Enabled (`PRAGMA foreign_keys = ON`), agents reference users and wallets

## Important Implementation Details

### Circle Wallet Provisioning
- **Wallet Set**: Created once per API instance, stored in app_config as `circle_wallet_set_id`
- **Per-Agent Wallet**: Each agent gets a unique Circle wallet on ARC-TESTNET
- **Address Format**: 42-character Ethereum-style hex address (0x-prefixed)
- **Payment Flow**: Nano-payments in USDC (Circle's stablecoin) with Circle TLS verification via `certifi`

### State Management in LangGraph
- **Orchestrator State**: Dict-based, accumulated across nodes with Command/Send for routing
- **Buyer Agent State**: Standard Python dict, nodes mutate and return output dict
- **Trace Recording**: execute_buyer_graph_with_trace captures input, output, and state snapshots at each node for UI visualization

### LLM Integration
- **Planner Model**: Llama-3.3-70B (via Featherless)
- **Seller Model**: Llama-3.1-8B (via Featherless)
- **Fallback**: If Featherless unavailable, seller uses stub research with pre-written answers
- **JSON Extraction**: Custom parser handles thinking tokens (`<think>` blocks) and markdown code fences

### Error Handling
- **Circle Errors**: Caught as CircleConfigApiException, CircleWalletApiException - fallback to in-memory if SDK unavailable
- **Task Failures**: Failed task_ids tracked, buyer workflows captured even on error for debugging
- **Retry Logic**: Some nodes have retry_count in state; currently set to 0 on start

## Common Tasks

**Add a new orchestrator node**: 
1. Create function `def my_node(state: OrchestratorState) -> dict`
2. Add to orchestrator/graph.py: `builder.add_node("my_node", my_node)`
3. Connect with `add_edge()` or `add_conditional_edges()`

**Add a buyer agent node**:
1. Create file `buyer_agent/nodes/my_step.py` with function
2. Update `buyer_agent/graph.py` node_sequence in execute_buyer_graph_with_trace
3. Add to builder StateGraph

**Modify database schema**:
1. Update SQL in `shared/database.py` initialize_database()
2. Migration: Will auto-apply on next app startup (idempotent CREATE TABLE IF NOT EXISTS)
3. Add repository methods in `shared/repository.py` for new tables

**Test a specific agent**:
1. Create test script in project root or tests/ directory
2. Use test_embedded.py as template (no server setup needed)
3. Call orchestrator_graph.invoke() directly with test state

## Configuration

All configuration via environment variables (loaded in `shared/config.py`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `CIRCLE_API_KEY` | - | Circle API authentication |
| `CIRCLE_ENTITY_SECRET` | - | Circle entity secret for wallets |
| `FEATHERLESS_API_KEY` | - | LLM API key for Featherless |
| `FEATHERLESS_BASE_URL` | `https://api.featherless.ai` | LLM endpoint |
| `DATABASE_FILE` | `data/marketplace.db` | SQLite database path |
| `PLANNER_MODEL` | `meta-llama/Llama-3.3-70B-Instruct` | Orchestrator LLM |
| `SELLER_MODEL` | `meta-llama/Llama-3.1-8B-Instruct` | Seller agent LLM |

Use `.env` file in project root for local development.

## Debugging Tips

- **Check DB state**: `sqlite3 data/marketplace.db ".tables"` then query tables directly
- **View agent execution trace**: Captured in BuyerWorkflowRecord.node_outputs
- **SSL/TLS issues**: Ensure `SSL_CERT_FILE="$(./venv312/bin/python -m certifi)"` before running servers
- **Port conflicts**: `lsof -i :8000` (API), `:8001` (seller), `:3000` (Next.js), `:8501` (Streamlit)
- **LLM response issues**: Check model availability and Featherless API key validity

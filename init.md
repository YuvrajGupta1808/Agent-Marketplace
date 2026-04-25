# Agent Marketplace Init

This file is the current working map of the repository. Treat it as the first file to read before changing code. Several older docs describe an earlier target architecture; this file is based on the files that exist in this checkout.

## Project Intent

Agent Marketplace is an autonomous commerce demo for buyer and seller agents on Arc Testnet. A user creates agents, gives a buyer a goal, the buyer decomposes the goal, pays a connected seller through Circle Programmable Wallets, sends a research request, receives the seller result, and synthesizes the final answer. The UI visualizes agent execution and payment history.

Core themes:

- LangGraph for agent workflow structure and traceable node execution.
- FastAPI for the marketplace API and seller research API.
- Circle developer-controlled wallets for real ARC-TESTNET USDC transfers.
- SQLite for local users, agents, wallets, app config, and transaction history.
- Vite/React frontend under `ui/`.

## Current Reality Check

Some existing docs are stale. Verify against code before relying on them.

- The frontend is Vite + React, not Next.js. Use `cd ui && npm run dev`.
- There is no root `package.json`; frontend commands run from `ui/`.
- `test_embedded.py`, `test_with_circle.py`, `demo/run_demo.py`, and root `app.py` are not present in this checkout.
- `start_servers.sh`, `README.md`, `QUICKSTART.md`, and parts of `CLAUDE.md` still reference missing scripts or older flows.
- Current API agent creation requires Circle credentials. There is no active in-memory payment fallback in the current `create_agent`, `sign_payment`, or `settle_payment` paths.
- `planner_mode` and `research_mode` exist in settings, but current buyer and seller LLM nodes mostly key off whether `FEATHERLESS_API_KEY` is present.

## Main Entry Points

Backend:

- `api/server.py`: public marketplace API. Owns `/users`, `/agents`, `/run`, `/run/stream`, `/transactions`, `/payments/{id}`, `/health`, `/resume`, and static serving of `ui/dist` when it exists.
- `seller_agent/server.py`: seller research API. Owns `/research` with payment enforcement and `/research/test` for unpaid seller testing.
- `scripts/start.py`: production-style startup. Seeds DB, then starts both API and seller uvicorn servers.
- `scripts/seed.py`: idempotent seed for a demo seller if Circle is configured.

Graphs:

- `orchestrator/graph.py`: currently a thin LangGraph wrapper with a single `buyer_agent_node`.
- `buyer_agent/graph.py`: main runtime for buyer workflows. The function `execute_buyer_graph_with_trace` is the important path used by the orchestrator and UI traces.
- `seller_agent/graph.py`: seller internal graph: retrieve context, run research, format response.

Shared infrastructure:

- `shared/config.py`: environment settings loaded from `.env`.
- `shared/database.py`: SQLite schema initialization and lightweight migrations.
- `shared/repository.py`: persistence methods for users, agents, wallets, app config, and transactions.
- `shared/circle_client.py`: Circle SDK wrapper.
- `shared/provisioning.py`: wallet set lookup/creation.
- `shared/x402_client.py`: local payment offer, authorization, and receipt models plus Circle-backed payment signing/settlement.
- `shared/types.py`: Pydantic API/domain models.

Frontend:

- `ui/src/App.tsx`: route table.
- `ui/src/lib/api.ts`: API client and DTOs.
- `ui/src/lib/app-state.tsx`: current user/buyer/seller/run state.
- `ui/src/pages/Builder.tsx`: buyer creation flow.
- `ui/src/pages/Dashboard.tsx`: run workflow/dashboard surface.
- `ui/src/components/dashboard/*`: execution graph, chat, transaction history, and node display.

## Runtime Flow

### API `/run`

1. `api/server.py` validates that `buyer_agent_id` exists and has role `buyer`.
2. If a `seller_agent_id` is provided, it validates that agent as a seller.
3. It invokes `orchestrator_graph` with:
   - `user_goal`
   - `thread_id`
   - `buyer_agent_id`
   - optional `seller_agent_id`
4. After the graph returns, it polls Circle for pending payment hashes when possible.
5. It returns `RunResponse`, including final answer, buyer workflow trace, payments, failed tasks, and transaction hashes.

### Orchestrator

Current `orchestrator/graph.py` is not a multi-node planner/dispatcher. It does this:

1. Load the buyer agent from SQLite.
2. Read connected seller IDs from buyer metadata.
3. Call `execute_buyer_graph_with_trace`.
4. Convert the result into `RunResponse`-compatible fields.

This means most orchestration behavior is inside `buyer_agent/graph.py`, not `orchestrator/nodes/`.

### Buyer Runtime

`execute_buyer_graph_with_trace` manually executes nodes and records `GraphNodeOutput` after each step:

1. `validate_scope`: uses buyer name, description, and system prompt to decide whether the goal is in scope. If no LLM key is set, accepts by default.
2. `decompose_goal`: uses Featherless/OpenAI-compatible API to split the goal into task dictionaries. If the LLM call or JSON parse fails, falls back to one task.
3. For each task:
   - `discover_seller`: chooses the first connected seller from buyer metadata, otherwise falls back to legacy `seller_agent_id`.
   - `execute_payment`: calls seller once to get HTTP 402 payment offer, signs authorization with Circle, creates Circle transfer, saves a transaction immediately.
   - `send_research_request`: calls seller again with payment headers.
   - `fetch_result`: normalizes seller response into `ResearchResult` and attaches payment receipt data.
4. `synthesize_results`: uses buyer identity and LLM to synthesize task results; falls back to concatenated summaries.

Important: the compiled `buyer_graph` at the bottom of `buyer_agent/graph.py` is not the path used by the API trace runner. Keep `execute_buyer_graph_with_trace` updated when changing buyer behavior.

### Seller Runtime

`seller_agent/server.py` enforces payment around `/research`:

1. Load seller agent from SQLite.
2. Build a `PaymentOffer` using seller wallet address and `SELLER_PRICE_USDC`.
3. If `PAYMENT-SIGNATURE` is missing, return HTTP 402 with `PAYMENT-REQUIRED` header.
4. Validate signed authorization and `PAYMENT-TX-ID`.
5. Fetch Circle transaction and validate destination and amount.
6. Invoke `seller_graph`.
7. Return graph result with `PAYMENT-RESPONSE` receipt header.

`seller_graph` is:

```text
START -> retrieve_context -> run_research -> format_response -> END
```

`retrieve_context` uses DuckDuckGo Instant Answer API. `run_research` uses Featherless via the OpenAI SDK when `FEATHERLESS_API_KEY` is present. It raises if no LLM key is configured, but catches generation errors and returns a minimal text response.

## Payment Model

The project uses a local x402-like pattern, not an imported x402 middleware package.

Headers defined in `shared/x402_client.py`:

- `PAYMENT-REQUIRED`
- `PAYMENT-SIGNATURE`
- `PAYMENT-TX-ID`
- `PAYMENT-RESPONSE`

Payment sequence:

1. Buyer posts to seller `/research` without payment headers.
2. Seller returns 402 and `PAYMENT-REQUIRED`.
3. Buyer signs typed payment data with Circle.
4. Buyer creates a Circle transfer from buyer wallet to seller wallet.
5. Buyer posts again with `PAYMENT-SIGNATURE` and `PAYMENT-TX-ID`.
6. Seller fetches Circle transaction and validates amount/destination before running research.
7. Buyer stores transaction in SQLite immediately in `execute_payment`.

Default local price is currently `SELLER_PRICE_USDC=0.01` in `shared/config.py` and `.env.example`; `render.yaml` overrides it to `0.001`.

## Database

SQLite path comes from `DATABASE_PATH`, defaulting to `data/marketplace.db`.

Tables initialized in `shared/database.py`:

- `app_config`: key/value app settings such as persisted Circle wallet set ID and seed markers.
- `users`: marketplace users.
- `wallets`: Circle wallet metadata for agents.
- `agents`: buyer/seller agents tied to users and wallets.
- `transactions`: Circle transfer records with thread/task/buyer/seller IDs.

`initialize_database()` also migrates old `agents` tables by adding `description` and `system_prompt` columns if missing.

## Environment

Local `.env` keys used by current code:

```bash
APP_ENV=development
API_HOST=127.0.0.1
API_PORT=8000
SELLER_HOST=127.0.0.1
SELLER_PORT=8001
SELLER_RESEARCH_PATH=/research
DATABASE_PATH=data/marketplace.db

ARC_CHAIN_ID=5042002
ARC_BLOCKCHAIN=ARC-TESTNET
ARC_RPC_URL=https://rpc.testnet.arc.network
ARC_EXPLORER_URL=https://testnet.arcscan.app
ARC_USDC_CONTRACT=0x3600000000000000000000000000000000000000

FEATHERLESS_API_KEY=...
FEATHERLESS_BASE_URL=https://api.featherless.ai/v1
ORCHESTRATOR_MODEL=meta-llama/Llama-3.3-70B-Instruct
SELLER_MODEL=meta-llama/Llama-3.1-8B-Instruct

CIRCLE_API_KEY=...
CIRCLE_ENTITY_SECRET=...
CIRCLE_WALLET_SET_ID=
CIRCLE_ACCOUNT_TYPE=EOA
CIRCLE_FEE_LEVEL=MEDIUM

SELLER_PRICE_USDC=0.01
REQUEST_TIMEOUT_SECONDS=90
```

Use `shared/ssl.py` or `SSL_CERT_FILE="$(./venv312/bin/python -m certifi)"` when Circle or HTTPS calls hit local TLS trust issues.

## Local Runbook

Install Python package and optional Circle dependencies:

```bash
./venv312/bin/python -m pip install -e '.[arc]'
```

Install frontend dependencies:

```bash
cd ui
npm install
```

Start seller API:

```bash
SSL_CERT_FILE="$(./venv312/bin/python -m certifi)" ./venv312/bin/python -m uvicorn seller_agent.server:app --host 127.0.0.1 --port 8001 --reload
```

Start marketplace API:

```bash
SSL_CERT_FILE="$(./venv312/bin/python -m certifi)" ./venv312/bin/python -m uvicorn api.server:app --host 127.0.0.1 --port 8000 --reload
```

Start frontend:

```bash
cd ui
npm run dev
```

Build frontend:

```bash
cd ui
npm run build
```

Run production-style local startup:

```bash
./venv312/bin/python scripts/start.py
```

Useful API checks:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/agents
curl 'http://127.0.0.1:8000/transactions'
```

## Verification Commands

There is no current automated Python test suite in the tree. For low-risk verification after code edits:

```bash
./venv312/bin/python -m compileall api buyer_agent orchestrator seller_agent shared scripts
cd ui && npm run lint
cd ui && npm run build
```

For end-to-end manual testing:

1. Ensure Circle credentials and Featherless key are configured.
2. Start seller and API servers.
3. Create a user through `/users` or the UI.
4. Create a seller agent through `/agents` or seed script.
5. Create a buyer with metadata `connected_seller_ids`.
6. Fund the buyer wallet on Arc Testnet if real transfers are required.
7. Call `/run` or use the dashboard.

## Known Sharp Edges

- `discover_seller` currently chooses a connected seller but does not return `seller_agent_id` into state. If `/run` omits `seller_agent_id`, later payment/request nodes may still see `seller_agent_id=None`. A likely fix is to return `"seller_agent_id": seller.id` from `discover_seller`.
- `api/server.py` streaming code checks for a node named `synthesize_answer`, but current `orchestrator_graph` only emits `buyer_agent_node` updates. Streaming final-result capture may need updating.
- `seller_agent/nodes/formatter.py` returns plain `output`, while `fetch_result` expects `response_body["result"]`. This can cause `fetch_result` errors unless the seller response shape is adjusted or `fetch_result` supports `output`.
- Agent metadata has overlapping fields. `CreateAgentRequest` has top-level `description` and `system_prompt`, but seed metadata also stores `description`, `use_case`, and `category`.
- `settings.research_mode` may say `stub`, but current seller research still requires `FEATHERLESS_API_KEY` for the primary path.
- `start_servers.sh` references missing demo/test scripts and a missing Streamlit `app.py`.
- `DEPLOYMENT.md` describes stub mode, but current wallet/payment code requires real Circle credentials for agent creation and payment settlement.

## Change Guidelines

- Prefer updating the actual runtime path first: `execute_buyer_graph_with_trace`, `api/server.py`, `seller_agent/server.py`, and `shared/*`.
- When changing buyer nodes, keep trace output useful because the UI depends on `BuyerWorkflowRecord.node_outputs`.
- When changing API models, update both `shared/types.py` and `ui/src/lib/api.ts`.
- When changing DB schema, update `shared/database.py` and add repository methods in `shared/repository.py`.
- When changing payment behavior, update both `shared/x402_client.py` and the seller validation in `seller_agent/server.py`.
- Keep older docs in mind, but treat source files and this init file as the current ground truth.

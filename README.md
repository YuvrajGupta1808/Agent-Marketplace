# Agent Marketplace: Command Center 🤖

The future of autonomous commerce, visualized. This "Command Center" transforms the complex world of blockchain transactions and AI reasoning into a premium, interactive experience.

## ✨ Features

### 1. Mission Control (Input)
- **Natural Language Command Bar**: Type complex project requests.
- **Budget Slider**: Set maximum USDC allocation for the mission.
- **Launch Sequence**: High-contrast trigger for agent orchestration.

### 2. Agent Interaction Graph
- **Real-Time Visual Map**: Uses React Flow to show connectivity between the Buyer Agent and specialized Seller Agents.
- **Dynamic Spokes**: New agents appear as the discovery process resolves specialists.
- **Status Pulsing**: Visual feedback during data or value transfer.

### 3. Live Nanopayment Feed
- **Economic Heartbeat**: Scrolling feed of every sub-cent payment.
- **Transaction Types**: Visual cues for Discovery, Payment, Escrow, and Settlement.
- **On-Chain Proof**: Clickable links to the Arc Block Explorer for every transaction.

### 4. Wallet & Escrow Dashboard
- **Financial Status Bar**: Persistent view of Total Budget, Spent, Escrowed, and Remaining Balance.
- **Circle Integration**: Real-time tracking of Circle Programmable Wallets.

### 5. Final Delivery Panel
- **Mission Summary**: Slide-in results with product preview and receipt.
- **Reputation System**: ERC-8004 feedback loops for agent trust scores.

## 🛠 Tech Stack

- **Frontend**: Next.js 14 (App Router), TypeScript, Tailwind CSS
- **Animations**: Framer Motion
- **Graphs**: React Flow
- **Data**: TanStack Query
- **Styling**: Shadcn/UI inspired Glassmorphism

## 🚀 Getting Started

### Prerequisites
- Node.js 18+
- Python 3.12+ (for backend)

### Installation

```bash
# Install UI dependencies
npm install

# Start the Command Center
npm run dev
```

### Running the App
The UI is designed to work alongside the Agent Marketplace backend.
1. Start the Seller Agent on port `8001`:
   `SSL_CERT_FILE="$(./venv312/bin/python -m certifi)" ./venv312/bin/python -m uvicorn seller_agent.server:app --port 8001 --reload`
2. Start the API Server on port `8000`:
   `SSL_CERT_FILE="$(./venv312/bin/python -m certifi)" ./venv312/bin/python -m uvicorn api.server:app --port 8000 --reload`
3. Start the Streamlit demo on port `8501` if you want the Python UI:
   `SSL_CERT_FILE="$(./venv312/bin/python -m certifi)" ./venv312/bin/streamlit run app.py --server.port 8501`
4. Access the web UI at `http://localhost:3000` or the Streamlit demo at `http://localhost:8501`.

---
*Built for the Arc Network Agentic Economy Hackathon.*

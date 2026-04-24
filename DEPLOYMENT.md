# Railway Deployment Guide

This document explains how to deploy Agent Marketplace to Railway, a free cloud platform supporting Python and Node.js applications.

## Platform Architecture

**Single Railway Service** running:
- FastAPI API server (public port, serves REST endpoints + Vite SPA)
- Seller Agent server (internal port 8001)
- SQLite database on persistent volume
- Automatic database seeding on first startup

## Prerequisites

1. **Railway Account**: Sign up at https://railway.app
2. **GitHub Repository**: This code must be pushed to GitHub
3. **Environment Variables**: You'll need:
   - Circle credentials: `CIRCLE_API_KEY`, `CIRCLE_ENTITY_SECRET`
   - LLM API key: `FEATHERLESS_API_KEY` (for live research mode)
   - Optional: `CIRCLE_WALLET_SET_ID` if you have an existing wallet set

## Step 1: Connect GitHub to Railway

1. Go to [railway.app/dashboard](https://railway.app/dashboard)
2. Click **"New Project"** → **"Deploy from GitHub"**
3. Authorize Railway to access your GitHub account
4. Select the `Agent-Marketplace` repository
5. Click **"Deploy"**

Railway will automatically detect `railway.toml` and begin building.

## Step 2: Add Persistent Volume

After the service deploys (or is building), you need a persistent volume for the SQLite database:

1. In Railway dashboard, open your project
2. Click the service name (e.g., "agent-marketplace")
3. Go to **"Volumes"** tab
4. Click **"+ New Volume"**
5. Set **Mount Path**: `/app/data`
6. Click **"Create"**

This ensures your database persists across deployments.

## Step 3: Configure Environment Variables

In the same service page, go to **"Variables"** tab and add:

### Required

```
CIRCLE_API_KEY=<your-circle-api-key>
CIRCLE_ENTITY_SECRET=<your-circle-entity-secret>
FEATHERLESS_API_KEY=<your-featherless-api-key>
DATABASE_PATH=/app/data/marketplace.db
```

### Optional (Railway auto-provides these, but shown for reference)

```
PORT=8000           (auto-set)
SELLER_PORT=8001
PLANNER_MODE=live
RESEARCH_MODE=live
SELLER_PRICE_USDC=0.001
REQUEST_TIMEOUT_SECONDS=60
APP_ENV=production
```

### For Stub Mode (if you don't have LLM credentials yet)

```
PLANNER_MODE=heuristic
RESEARCH_MODE=stub
FEATHERLESS_API_KEY=<can-be-empty>
```

In stub mode, the seller agent responds with pre-written research answers without calling an LLM.

## Step 4: Verify Deployment

Once the build completes:

1. Click the **"Deploy"** tab to see build logs
2. Look for output like:
   ```
   ✓ Seeding complete!
   🚀 Starting servers...
     API server: http://0.0.0.0:8000
     Seller agent: http://0.0.0.0:8001
   ✓ Servers started. Waiting for requests...
   ```

3. Get your public URL from the Railway dashboard (e.g., `https://agent-marketplace-prod-xxx.railway.app`)
4. Test the health endpoint:
   ```bash
   curl https://your-railway-url/health
   ```
   Should return: `{"circle_enabled": true, ...}`

## Step 5: Fund Wallets (for Circle Payments)

When the app first starts, it seeds the database with a demo seller and buyer agent. Each gets a Circle wallet on Arc Testnet. The seller's address is printed in the startup logs.

To enable live payments:

1. Get the seller wallet address from Railway logs
2. Go to [Arc Testnet Faucet](https://faucet.testnet.arc.network/) (or equivalent)
3. Send test USDC to the seller's wallet address

The buyer also gets a wallet; fund it similarly if you want to test the complete payment flow.

## Step 6: Access the Application

Open your Railway URL in a browser:
```
https://your-service-name.railway.app
```

The Vite SPA frontend will load at the root path. You can:
1. Register a new user
2. Create a buyer agent (auto-provisions a Circle wallet)
3. Run queries to the demo seller agent
4. View live transaction history

## Local Testing Before Deployment

To test locally before pushing to Railway:

```bash
# Install dependencies
pip install -e .
cd ui && npm ci && npm run build && cd ..

# Set environment variables (optional for stub mode)
export FEATHERLESS_API_KEY=xxx
export CIRCLE_API_KEY=xxx
export CIRCLE_ENTITY_SECRET=xxx

# Run the startup script (seeds DB + starts servers)
python scripts/start.py
```

Then open `http://localhost:8000` in your browser.

## Troubleshooting

### Deployment Fails with "Python version not found"

Railway's Nixpacks builder detects Python 3.12 automatically. If it fails:
1. Check `nixpacks.toml` exists in repo root (it should)
2. Verify the build environment is set to "Nixpacks" (not "Heroku")
3. Force a rebuild: Railway dashboard → Redeploy

### Seeding Fails with Circle Error

If the seed script fails to create wallets:
1. Check `CIRCLE_API_KEY` and `CIRCLE_ENTITY_SECRET` are valid
2. Ensure Circle credentials have "Developer Controlled Wallets" permission
3. Check the build logs for the exact Circle error message
4. If credentials are missing, set `CIRCLE_API_KEY` and `CIRCLE_ENTITY_SECRET` as empty strings — the app falls back to stub mode

### Database Not Persisting

If the SQLite database disappears after redeploy:
1. Verify the volume is mounted at `/app/data`
2. Check `DATABASE_PATH=/app/data/marketplace.db` env var is set
3. In Railway dashboard, confirm the volume shows non-zero usage

### "No seller agents online"

This means the seed script ran but `CIRCLE_ENABLED=false`. Either:
1. Set Circle credentials, or
2. Manually create a seller agent via the API:
   ```bash
   curl -X POST https://your-url/agents \
     -H "Content-Type: application/json" \
     -d '{"user_id": "demo-user-id", "name": "Demo Seller", "role": "seller"}'
   ```

## Environment Variables Reference

| Variable | Default | Purpose |
|---|---|---|
| `CIRCLE_API_KEY` | - | Circle Programmable Wallets API key |
| `CIRCLE_ENTITY_SECRET` | - | Circle entity secret for wallet operations |
| `FEATHERLESS_API_KEY` | - | LLM API key for live research |
| `DATABASE_PATH` | `data/marketplace.db` | SQLite database file path |
| `PORT` | `8000` | Public API port (set by Railway) |
| `SELLER_PORT` | `8001` | Internal seller agent port |
| `PLANNER_MODE` | `heuristic` | `heuristic` (fast) or `live` (LLM-based) |
| `RESEARCH_MODE` | `stub` | `stub` (mock answers) or `live` (LLM-based) |
| `SELLER_PRICE_USDC` | `0.001` | Price per research task in USDC |
| `FEATHERLESS_BASE_URL` | `https://api.featherless.ai/v1` | LLM endpoint |
| `ORCHESTRATOR_MODEL` | `meta-llama/Llama-3.3-70B-Instruct` | Planning model |
| `SELLER_MODEL` | `meta-llama/Llama-3.1-8B-Instruct` | Research model |

## Monitoring

Railway provides a dashboard to monitor:
- **Build logs**: Check for errors during build/seed
- **Deployment logs**: See server startup and runtime issues
- **Metrics**: CPU, memory, and request rate
- **Deployments**: Rollback to previous versions if needed

## Cost

Railway's free tier includes:
- **$5/month free credit**
- A small Python service typically costs $1-3/month
- This project stays within the free tier

If you exceed the free credit, Railway will notify you before charging.

## Redeploying After Code Changes

After pushing new code to GitHub:

1. Railway will **automatically redeploy** (if auto-deploy is enabled)
2. Or manually trigger in the Railway dashboard: **"Redeploy"** button
3. The seed script is idempotent — it skips if already seeded, so DB isn't reset

## Next Steps

- **Customize the landing page** with your branding (ui/src/pages/Landing.tsx)
- **Add more sellers** by creating new seller agents in the dashboard
- **Integrate your own LLM** by updating `FEATHERLESS_API_KEY` and model names
- **Track metrics** with Railway's built-in monitoring

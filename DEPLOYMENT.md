# Render Deployment Guide

This document explains how to deploy Agent Marketplace to Render, a free cloud platform supporting Python and Node.js applications.

## Platform Architecture

**Single Render Web Service** running:
- FastAPI API server (public port, serves REST endpoints + Vite SPA)
- Seller Agent server (internal port 8001)
- SQLite database on persistent disk (1GB)
- Automatic database seeding on first startup

## Prerequisites

1. **Render Account**: Sign up at https://render.com (free)
2. **GitHub Repository**: This code must be pushed to GitHub (already done)
3. **Environment Variables**: You'll need:
   - Circle credentials: `CIRCLE_API_KEY`, `CIRCLE_ENTITY_SECRET` (optional for stub mode)
   - LLM API key: `FEATHERLESS_API_KEY` (optional for live research mode)

## Important: Free Tier Limitations

Render's free tier has two important characteristics:

1. **Services spin down after 15 minutes of inactivity** — If no requests come in for 15 min, the service goes to sleep. The next request wakes it up (takes ~30 sec).
2. **Limited resources** — Shared CPU, 512MB RAM. Fine for a demo, but not production.

**Workaround**: Use an uptime monitoring service (like [Uptime Robot](https://uptimerobot.com)) to ping `/health` every 10 minutes to keep the service awake.

## Step 1: Connect GitHub to Render

1. Go to [render.com/dashboard](https://dashboard.render.com/)
2. Click **"+ New"** → **"Web Service"**
3. Select **"GitHub"** as the repository source
4. Authorize Render to access your GitHub account
5. Search for and select the `Agent-Marketplace` repository
6. Click **"Connect"**

## Step 2: Configure the Service

Render will auto-detect the `render.yaml` file. Verify these settings:

**Basic:**
- Name: `agent-marketplace` (or any name you prefer)
- Runtime: `Python 3.12`
- Build Command: (auto-filled from render.yaml)
- Start Command: `python scripts/start.py`
- Plan: **Free**

**Health Check:**
- Path: `/health`
- Check interval: 30 seconds

The `render.yaml` file already specifies the persistent disk and environment variables. Render will apply these automatically.

## Step 3: Add Secrets (Environment Variables)

In the Render dashboard for your service, go to **"Environment"** and add:

### Stub Mode (Free, No API Keys Needed)

```
CIRCLE_API_KEY=<leave empty or any string>
CIRCLE_ENTITY_SECRET=<leave empty or any string>
FEATHERLESS_API_KEY=<leave empty or any string>
```

The app will work in stub mode:
- Planner uses heuristic (fast)
- Researcher returns pre-written answers (no LLM calls)
- Circle wallets are simulated (no real USDC transfers)

### Live Mode (Requires API Keys)

If you have Circle and Featherless API keys:

```
CIRCLE_API_KEY=<your-circle-api-key>
CIRCLE_ENTITY_SECRET=<your-circle-entity-secret>
FEATHERLESS_API_KEY=<your-featherless-api-key>
```

Leave the rest of the env vars as defaults (they're in render.yaml).

## Step 4: Deploy

1. Click **"Create Web Service"**
2. Render will start building (watch the logs)
3. Build takes ~3-5 minutes (Node.js + Python dependencies)
4. Look for output like:
   ```
   ✓ Seeding complete!
   🚀 Starting servers...
     API server: http://0.0.0.0:8000
     Seller agent: http://0.0.0.0:8001
   ✓ Servers started. Waiting for requests...
   ```

5. Once deployed, you'll get a public URL: `https://agent-marketplace-xxx.onrender.com`

## Step 5: Keep the Service Awake (Optional but Recommended)

Since Render free services spin down, set up an uptime monitor:

1. Go to [uptimerobot.com](https://uptimerobot.com) (free tier available)
2. Create a new "HTTP(s) Monitor"
3. URL: `https://your-service.onrender.com/health`
4. Interval: `10 minutes`
5. This keeps your service alive even if no one is actively using it

## Step 6: Access the Application

Open your Render service URL in a browser:
```
https://agent-marketplace-xxx.onrender.com
```

The Vite SPA frontend will load. You can:
1. Register a new user
2. Create a buyer agent (auto-provisions a Circle wallet if enabled)
3. Run queries to the demo seller agent
4. View live transaction history

## Stub Mode vs Live Mode

### Stub Mode (Default)
- No API keys needed ✓
- Fast responses (heuristic planner, pre-written research) ✓
- No real USDC transfers (simulated Circle wallets) ✓
- Great for demos and testing ✓

**Use this if you just want to see the app working.**

### Live Mode
- Requires `CIRCLE_API_KEY`, `CIRCLE_ENTITY_SECRET`, `FEATHERLESS_API_KEY`
- Real LLM-based planning and research
- Real USDC transfers on Arc Testnet (needs wallet funding)
- Full agent autonomy

**Use this to showcase real agent capabilities.**

## Local Testing Before Deployment

To test locally before pushing to Render:

```bash
# Install dependencies
pip install -e .
cd ui && npm ci && npm run build && cd ..

# Run the startup script (seeds DB + starts servers)
python scripts/start.py
```

Then open `http://localhost:8000` in your browser.

The `render.yaml` file specifies all config needed. Render will apply it automatically when you deploy.

## Troubleshooting

### Deployment Fails During Build

Check the build logs in Render dashboard. Common issues:

1. **Node.js build fails** → Missing Node version or npm script error
   - Fix: Check `ui/package.json` build script
   
2. **Python install fails** → pyproject.toml syntax error or missing deps
   - Fix: Test locally with `pip install -e .`

3. **Timeout** → Dependencies taking too long
   - Check internet connection, try redeploying

### "Services failing to start"

1. Check the startup logs for errors from `python scripts/seed.py` or `uvicorn`
2. Verify env vars are set correctly (especially if Circle keys are empty)
3. Check that the disk is mounted at `/var/data`

### Disk Not Mounting

If the database doesn't persist across redeploys:

1. In Render dashboard, go to your service
2. Click **"Disks"** tab
3. Verify a disk is attached at mount path `/var/data`
4. If missing, add one: **"Add Disk"** → Mount path `/var/data`, Size `1 GB`

### Service Keeps Spinning Down

Free tier services sleep after 15 minutes of inactivity. This is expected. To keep it always awake:

1. Set up an uptime monitor (see Step 5)
2. Or trigger a request every 10 minutes manually
3. Or upgrade to a paid Render plan ($7/month) for always-on

### "No seller agents online"

The seed script created them, but they may not show on the frontend if Circle is disabled. This is normal in stub mode. The agents exist in the database and work for queries.

## Environment Variables Reference

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_PATH` | `/var/data/marketplace.db` | SQLite database file |
| `CIRCLE_API_KEY` | _(empty)_ | Circle API key (stub mode if empty) |
| `CIRCLE_ENTITY_SECRET` | _(empty)_ | Circle entity secret |
| `FEATHERLESS_API_KEY` | _(empty)_ | LLM API key (stub mode if empty) |
| `SELLER_PORT` | `8001` | Internal seller agent port |
| `PLANNER_MODE` | `heuristic` | `heuristic` (fast) or `live` (LLM) |
| `RESEARCH_MODE` | `stub` | `stub` (mock) or `live` (LLM) |
| `SELLER_PRICE_USDC` | `0.001` | Price per research task |
| `REQUEST_TIMEOUT_SECONDS` | `60` | Request timeout |
| `APP_ENV` | `production` | Environment name |

## Cost

**Completely free forever** on Render's free tier. No credit card required (though you can upgrade to paid if desired).

Limitations of free tier:
- Services spin down after 15 min inactivity
- Shared infrastructure (slow startup, but works)
- 0.5 GB RAM (enough for this app)

## Monitoring

Render provides a dashboard to view:
- **Build logs**: Any build errors
- **Runtime logs**: Server startup and request logs
- **Metrics**: CPU and memory usage
- **Disk usage**: Current database size

## Redeploying After Code Changes

After pushing new code to GitHub:

1. Render will **automatically redeploy** if auto-deploy is enabled
2. Or manually trigger: Dashboard → Service → **"Manual Deploy"**
3. The seed script is idempotent — DB isn't reset on redeploy

## Next Steps

- **Set up uptime monitoring** (Uptime Robot) to keep service alive
- **Customize the landing page** (ui/src/pages/Landing.tsx)
- **Add Circle credentials** if you have them (for live mode)
- **Fund wallets** with test USDC if using live mode

## Free vs Paid

| Feature | Free | Paid ($7+/month) |
|---|---|---|
| Always awake | ❌ Spins down after 15 min | ✓ Always running |
| Memory | 512 MB shared | 1 GB+ dedicated |
| Support | Community | Priority |
| Custom domain | ❌ | ✓ |
| Environment | Great for demos | Production-ready |

For a demo project, free is perfect. Upgrade if you need always-on uptime.

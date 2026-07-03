# 短线精灵

短线精灵是一个加密市场短线机会扫描与模拟观察工具。系统默认扫描 CoinGecko 市值前 100 个标的，按机会分、趋势、流动性和风险排序，并用模拟仓位观察策略效果。

## Stack

- Frontend: Next.js, TypeScript, Tailwind CSS
- Backend: FastAPI, SQLAlchemy
- Database: PostgreSQL
- Data source: CoinGecko `/coins/markets` and market chart data
- Optional AI: OpenAI summary generation, with mock summaries when `OPENAI_API_KEY` is missing

## Features

- Dashboard page at `/`
- Dynamic asset detail pages at `/asset/{symbol}`
- Paper trading observation page at `/paper`
- Current price, 24h change, market cap, 24h volume
- AI score, trend score, liquidity score, risk score
- Opportunity score, direction, trigger price, stop loss, take profit
- 4H K-line chart with MA, Vegas, Fib, DT, support/resistance overlays
- AI summary paragraph
- Watchlist and opportunity table for the top 100 assets
- Paper trading: 10000 USDT account, 500 USDT margin per trade, 5x leverage
- Automatic backend refresh every 30 minutes
- Refresh endpoint for cron or hosted schedulers

## Quick Start With Docker

```bash
docker compose up --build
```

Load market data:

```bash
curl -X POST http://localhost:8000/scheduler/refresh -H "x-refresh-token: change-me"
```

Open:

- Frontend: http://localhost:3000
- Backend docs: http://localhost:8000/docs

## Production Deploy On DigitalOcean

Recommended deployment shape:

- One DigitalOcean Droplet running Docker Compose
- PostgreSQL only inside Docker network, not exposed to the public internet
- Caddy reverse proxy on ports 80 and 443
- GoDaddy domain DNS `A` record pointing to the Droplet public IPv4
- Backend refresh loop enabled every 30 minutes

### 1. Point Your Domain To The Droplet

In GoDaddy DNS settings:

- Type: `A`
- Name: `@`
- Value: your Droplet public IPv4
- TTL: default is fine

Optional `www` record:

- Type: `CNAME`
- Name: `www`
- Value: your root domain, for example `your-domain.com`

Wait until DNS resolves before starting HTTPS. This can take a few minutes, sometimes longer.

### 2. Install Docker On The Droplet

On Ubuntu:

```bash
apt update
apt install -y docker.io docker-compose-plugin git
systemctl enable docker
systemctl start docker
docker --version
docker compose version
```

### 3. Upload Or Clone The Project

Put this project on the server, for example:

```bash
mkdir -p /opt/shortline-spirit
cd /opt/shortline-spirit
```

If using git, clone the repository here. If uploading files manually, upload the full project folder contents.

### 4. Create Production Env

```bash
cp .env.production.example .env.production
nano .env.production
```

Set at least:

```env
DOMAIN=your-domain.com
PUBLIC_ORIGIN=https://your-domain.com
POSTGRES_PASSWORD=use-a-long-random-password
REFRESH_TOKEN=use-a-long-random-token
```

Optional:

```env
COINGECKO_API_KEY=your-coingecko-key
OPENAI_API_KEY=your-openai-key
```

If `OPENAI_API_KEY` is empty, the app uses mock AI summaries.

### 5. Start Production

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up --build -d
```

Check containers:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml ps
```

Watch logs:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml logs -f
```

### 6. First Market Refresh

Run this once after the containers are up:

```bash
curl -X POST https://your-domain.com/api/scheduler/refresh -H "x-refresh-token: use-a-long-random-token"
```

After that, the backend refreshes automatically every 30 minutes when `AUTO_REFRESH_ENABLED=true`.

### 7. Update The App Later

After changing code:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up --build -d
```

### Production Notes

- Keep ports `80` and `443` open in the DigitalOcean firewall.
- Do not expose PostgreSQL port `5432` publicly.
- Keep `.env.production` private.
- The public backend API is available under `/api/*`, for example `/api/assets`.
- This project is still a research and simulation tool, not an automated real trading system.

## Local Development

Start PostgreSQL, then create `backend/.env`:

```bash
cp backend/.env.example backend/.env
```

Install and run the API:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Create `frontend/.env.local`:

```bash
cp frontend/.env.example frontend/.env.local
```

Install and run the frontend:

```bash
cd frontend
npm install
npm run dev
```

## Refresh Endpoint

Use either endpoint:

- `POST /refresh`
- `POST /scheduler/refresh`

If `REFRESH_TOKEN` is set, pass it as:

```bash
x-refresh-token: your-token
```

Example cron entry:

```cron
*/15 * * * * curl -s -X POST http://localhost:8000/scheduler/refresh -H "x-refresh-token: change-me" >/dev/null
```

## Environment Variables

Backend:

- `DATABASE_URL`
- `COINGECKO_BASE_URL`
- `COINGECKO_API_KEY`
- `OPENAI_API_KEY`
- `REFRESH_TOKEN`
- `CORS_ORIGINS`

Frontend:

- `NEXT_PUBLIC_API_BASE_URL`

## Notes

The score model is intentionally simple for MVP research triage:

- Trend score is driven by 24h percentage change.
- Liquidity score is driven by 24h volume relative to market cap.
- Risk score rises with short-term volatility and eases with stronger liquidity.
- AI score blends trend, liquidity, and inverse risk.

This project is for research workflow prototyping only and is not financial advice.

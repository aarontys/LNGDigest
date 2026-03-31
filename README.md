# LNG Intelligence Pipeline — Railway Deployment Guide

## Files in this package
- `lng_digest.py` — main script (daily digest + weekly + monthly summaries)
- `requirements.txt` — Python dependencies
- `railway.toml` — Railway deployment config
- `README.md` — this file

---

## ⚠️ Before You Deploy — Rotate Your Credentials

Your old credentials were stored in plain text. Replace them with fresh ones:

1. **Anthropic API key**: https://console.anthropic.com → API Keys → delete old key → create new
2. **Telegram bot token**: Message @BotFather → /mybots → select your bot → API Token → Revoke & regenerate

---

## Step-by-Step Railway Deployment

### 1. Create a GitHub repository
- Go to github.com → New repository → name it `lng-digest` → Private → Create
- Upload all 4 files from this package (drag and drop into the repo)

### 2. Sign up for Railway
- Go to railway.app → "Start a New Project" → Login with GitHub

### 3. Create a new project
- Click "New Project" → "Deploy from GitHub repo"
- Select your `lng-digest` repository
- Railway will detect the `railway.toml` and auto-configure

### 4. Set environment variables (your credentials go here — NOT in code)
In the Railway dashboard → your service → "Variables" tab → add these 3:

| Variable Name        | Value                        |
|----------------------|------------------------------|
| `TELEGRAM_BOT_TOKEN` | your new bot token           |
| `TELEGRAM_CHAT_ID`   | XXXX                   |
| `ANTHROPIC_API_KEY`  | your new Anthropic API key   |

### 5. Deploy
- Railway auto-deploys when you save variables
- Click "Deploy" if it doesn't start automatically
- Watch the logs — you should see a test digest fire within ~30 seconds
- Check your Telegram — the first message should arrive immediately

---

## Schedule (Singapore Time, SGT / UTC+8)
| Report          | When                          |
|-----------------|-------------------------------|
| Daily digest    | Every day at 07:00 SGT        |
| Weekly summary  | Every Monday at 07:30 SGT     |
| Monthly report  | 1st of each month at 08:00 SGT|

---

## Monitoring
- Railway dashboard → your service → "Logs" tab shows real-time output
- Errors appear in red — most common: Anthropic credit balance, Telegram token issues

## Costs
- Railway free tier: ~$0.50/month for this workload (well within $5/month allowance)
- Anthropic API: ~$0.10–0.30/month depending on article volume

---

## Local testing (Windows)
```
pip install feedparser requests anthropic
set TELEGRAM_BOT_TOKEN=your_token
set TELEGRAM_CHAT_ID=1037738009
set ANTHROPIC_API_KEY=your_key
python lng_digest.py
```

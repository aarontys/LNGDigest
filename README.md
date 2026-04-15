# LNG Intelligence Pipeline

Automated LNG industry briefings and job alerts delivered to Telegram, powered by Claude AI.

Pulls ~14 RSS feeds, filters for LNG-relevant articles, generates executive-style summaries grouped by category, and sends them to one or more Telegram recipients on a configurable schedule. Separately monitors job boards for LNG/energy trading roles.

## Architecture

```
NEWS DIGEST                              JOB SCRAPER
RSS Feeds (14 sources)                   Job Feeds (Indeed, Energy Jobline, Rigzone)
    ↓  feedparser                            ↓  feedparser
Keyword Filter → Dedup                   Keyword Filter → Dedup (seen_jobs.json)
    ↓  (seen_articles.json)                  ↓
Google News URL Resolver                 Target Company Matching
    ↓                                        ↓
Claude AI Summary                        Format Alert
    ↓                                        ↓
Telegram Bot → All Recipients            Telegram Bot → Job Recipients
```

**Stack:** Python 3.12+, feedparser, Anthropic API, Telegram Bot API
**Hosting:** Railway.app (always-on, GitHub-connected)
**Timezone:** SGT (UTC+8)

## Files

| File | Purpose |
|------|---------|
| `lng_digest.py` | Main script — news digest + scheduler (also runs job checks) |
| `lng_jobs.py` | Job scraper — polls job feeds, filters, sends alerts |
| `digest_config.py` | **Single source of truth** — all settings for both digest and jobs |
| `requirements.txt` | Python dependencies |
| `railway.toml` | Railway deployment config |
| `seen_articles.json` | Auto-created — news dedup hashes |
| `seen_jobs.json` | Auto-created — job dedup hashes |
| `article_history.json` | Auto-created — 30-day article archive (for future weekly/monthly) |

## Schedule

Default times (edit in `digest_config.py`):

| Time (SGT) | What |
|------------|------|
| 7:30 AM | Job check — catch overnight postings |
| 8:00 AM | Morning news briefing |
| 12:00 PM | Midday news update |
| 3:00 PM | Afternoon news update |
| 6:00 PM | Job check — catch daytime postings |
| 9:25 PM | Evening news update |

## Railway Deployment

### 1. GitHub repo

Push all files to a private GitHub repo.

### 2. Railway setup

1. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub repo
2. Select your repository — Railway detects `railway.toml` automatically

### 3. Environment variables

In Railway dashboard → your service → **Variables** tab, add:

| Variable | Value |
|----------|-------|
| `TELEGRAM_BOT_TOKEN` | Your bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Your Telegram user ID |
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `COLLEAGUE_TELEGRAM_CHAT_ID` | (Optional) Colleague's Telegram user ID |

### 4. Deploy

Railway auto-deploys on push. Check **Logs** tab for:
```
🟢 LNG Digest service started
   Job scraper: 7:30, 18:00 SGT
   News schedule: 8:00, 12:00, 15:00, 21:25 SGT
   Recipients: ['Aaron', 'Jennifer']
```

## Local Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Set credentials
export TELEGRAM_BOT_TOKEN="your_token"
export TELEGRAM_CHAT_ID="your_id"
export ANTHROPIC_API_KEY="your_key"

# Send one news digest immediately
python lng_digest.py --test

# Run one job check immediately
python lng_digest.py --test-jobs

# Test all news RSS feeds
python lng_digest.py --diagnose

# Test all job feeds
python lng_jobs.py --diagnose

# Start the full scheduler (news + jobs)
python lng_digest.py
```

On Windows, use `set` instead of `export`.

## Job Scraper

The job scraper monitors RSS feeds from Indeed (Singapore, Houston, London, Tokyo), Energy Jobline, and Rigzone. It filters for LNG and energy trading keywords and highlights postings from target companies.

### How it works

1. Polls job feeds at configured times (default: 7:30 AM and 6:00 PM SGT)
2. Filters by job-specific keywords (role titles, not just company names)
3. Deduplicates against `seen_jobs.json` — you only see each posting once
4. Highlights target companies (JERA, Shell, Trafigura, Vitol, etc.) with a ⭐
5. Sends alert to `JOB_RECIPIENTS` (just you by default, not colleagues)

### Adding company career page coverage via Google Alerts

Most IOCs and trading houses (Shell, BP, Trafigura, etc.) use Workday portals that don't offer RSS. To catch their postings when Google indexes them:

1. Go to [google.com/alerts](https://www.google.com/alerts)
2. Create an alert, e.g. `Shell LNG careers OR jobs`
3. Click "Show options" → set **Deliver to: RSS feed**
4. Copy the RSS feed URL (right-click the RSS icon → Copy link address)
5. Paste the URL into `JOB_FEEDS` in `digest_config.py`
6. Repeat for each target company

Suggested alerts to create:
- `Shell LNG careers OR jobs`
- `BP LNG careers OR jobs`
- `TotalEnergies LNG careers OR jobs`
- `Trafigura LNG OR gas careers OR jobs`
- `Woodside LNG careers OR jobs`
- `JERA LNG careers OR jobs`
- `Pavilion Energy careers OR jobs`
- `Cheniere LNG careers OR jobs`
- `Vitol energy trading careers OR jobs`

### Customising

Edit `digest_config.py`:
- `JOB_FEEDS` — add/remove job board RSS URLs or Google Alert feeds
- `JOB_KEYWORDS` — job-specific terms that must match in title/description
- `JOB_TARGET_COMPANIES` — companies flagged with ⭐ when matched
- `JOB_RECIPIENTS` — who gets job alerts (separate from news recipients)
- `JOB_TIMES` — when to check for new postings

## Adding a Colleague

1. Have them message your bot in Telegram, then get their user ID via [@userinfobot](https://t.me/userinfobot)
2. Add `COLLEAGUE_TELEGRAM_CHAT_ID = their_id` in Railway Variables
3. Add their line in `digest_config.py` under `TELEGRAM_RECIPIENTS`
4. Push to GitHub — Railway auto-deploys

Job alerts go only to `JOB_RECIPIENTS` by default (just you).

## Google News URL Resolution

Google News RSS returns opaque redirect URLs (`https://news.google.com/rss/articles/CBMi...`) instead of direct article links. The news digest resolves these using three strategies (in order): extracting the article URL from `<a href>` tags in the RSS description HTML, decoding the Base64-encoded payload in the URL path, and falling back to HTTP redirect following. The first two are fast and don't make network calls.

## Costs

- **Railway:** ~$0.50/month (well within free tier)
- **Anthropic API:** ~$0.10–0.30/month depending on article volume

## Troubleshooting

| Issue | Fix |
|-------|-----|
| No messages arriving | Check `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in Railway Variables |
| `403 Forbidden` in logs | Bot token is wrong or expired — regenerate via @BotFather |
| `can't parse entities` | Markdown formatting issue — the script auto-retries as plain text |
| Empty digests | Run `python lng_digest.py --diagnose` to check feeds |
| No job alerts | Run `python lng_jobs.py --diagnose` to check job feeds |
| Google News URLs still opaque | Run `--diagnose` to check; Base64 decode handles most cases but some may resist |
| Colleague not receiving | Verify their chat ID with @userinfobot; check Railway logs |

## Roadmap

- [ ] **Weekly summaries** — Monday 7:30 AM SGT, pattern analysis across 7 days
- [ ] **Monthly strategic report** — 1st of month 8:00 AM SGT
- [ ] LinkedIn saved search email parsing (LinkedIn doesn't offer RSS)
- [ ] MyCareersFuture scraping (Singapore gov job board, no RSS)
- [ ] Company career page polling (JERA, Woodside, Pavilion, etc.)
- [ ] Substack author monitoring
- [ ] Gmail newsletter digest integration
- [ ] PDF report ingestion (IGU, GIGNL)

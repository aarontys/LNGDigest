"""
lng_digest.py — Personal LNG Morning Intelligence Briefing
===========================================================
Pulls RSS feeds, summarizes with Claude AI, delivers to Telegram daily.

Cloud deployment: Railway.app
Timezone: Singapore (SGT, UTC+8)
Schedule: Daily 07:00 SGT | Weekly Monday 07:30 SGT | Monthly 1st 08:00 SGT
"""

import feedparser
import requests
import time
import json
import hashlib
import os
import logging
import sys
import anthropic
from datetime import datetime, timezone, timedelta

# ── Credentials from environment variables (set in Railway dashboard) ──────────
TELEGRAM_BOT_TOKEN   = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID     = os.environ["TELEGRAM_CHAT_ID"]
ANTHROPIC_API_KEY    = os.environ["ANTHROPIC_API_KEY"]

# ── Settings ───────────────────────────────────────────────────────────────────
SGT                  = timezone(timedelta(hours=8))   # Singapore Time (UTC+8)
DAILY_HOUR           = 7
DAILY_MINUTE         = 0
WEEKLY_HOUR          = 7
WEEKLY_MINUTE        = 30
MONTHLY_HOUR         = 8
MONTHLY_MINUTE       = 0
MAX_ARTICLES_PER_RUN = 30
SEEN_FILE            = "seen_articles.json"
HISTORY_FILE         = "article_history.json"

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("lng_digest.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ── Anthropic client ───────────────────────────────────────────────────────────
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ── RSS Feeds ──────────────────────────────────────────────────────────────────
RSS_FEEDS = [
    "https://www.lngprime.com/feed/",
    "https://www.naturalgasintel.com/feed/",
    "https://oilprice.com/rss/main",
    "https://energymonitor.ai/feed/",
    "https://feeds.reuters.com/reuters/businessNews",
    "https://feeds.reuters.com/reuters/companyNews",
    "https://feeds.reuters.com/Reuters/worldNews",
    "https://www.offshore-energy.biz/feed/",
    "https://www.upstreamonline.com/rss",
]

# ── LNG Keywords ───────────────────────────────────────────────────────────────
KEYWORDS = [
    "LNG", "liquefied natural gas", "LNG terminal", "LNG tanker",
    "LNG export", "LNG import", "LNG price", "LNG cargo", "LNG carrier",
    "LNG regasification", "LNG liquefaction", "LNG bunkering", "FSRU",
    "natural gas market", "gas supply", "gas prices", "JKM", "TTF",
    "Henry Hub", "Sabine Pass", "Freeport LNG", "Qatar Energy",
    "Shell LNG", "TotalEnergies LNG", "BP gas",
]

# ── Categories ─────────────────────────────────────────────────────────────────
CATEGORIES = {
    "📊 Market Prices & Trade Flows": [
        "price", "spot", "cargo", "trade", "export", "import",
        "shipment", "tanker", "supply", "demand", "henry hub", "ttf", "jkm",
    ],
    "🌍 Policy & Geopolitics": [
        "policy", "sanction", "government", "geopolit", "treaty",
        "regulation", "minister", "summit", "war", "conflict", "election",
    ],
    "🏗️ Infrastructure & Terminals": [
        "terminal", "regasification", "liquefaction", "fsru", "pipeline",
        "port", "construction", "capacity", "infrastructure", "project", "plant",
    ],
    "🏢 Company News & Deals": [
        "deal", "acquisition", "merger", "contract", "agreement",
        "partnership", "investment", "company", "corp", "ipo", "quarterly", "earnings",
    ],
}


# ══════════════════════════════════════════════════════════════════════════════
#  ARTICLE HISTORY  (for weekly/monthly summaries)
# ══════════════════════════════════════════════════════════════════════════════
def load_history() -> list:
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return []

def save_to_history(articles: list):
    history  = load_history()
    now_iso  = datetime.now(SGT).isoformat()
    for a in articles:
        a["saved_at"] = now_iso
    history.extend(articles)
    # Keep only last 35 days to control file size
    cutoff  = datetime.now(SGT) - timedelta(days=35)
    history = [
        a for a in history
        if datetime.fromisoformat(a.get("saved_at", now_iso)) > cutoff
    ]
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f)


# ══════════════════════════════════════════════════════════════════════════════
#  FETCH ARTICLES
# ══════════════════════════════════════════════════════════════════════════════
def load_seen() -> set:
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()

def save_seen(seen: set):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

def fetch_articles(hours: int = 26) -> list:
    seen     = load_seen()
    articles = []
    cutoff   = datetime.now(timezone.utc) - timedelta(hours=hours)

    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:15]:
                url = entry.get("link", "")
                uid = hashlib.md5(url.encode()).hexdigest()
                if uid in seen:
                    continue

                title   = entry.get("title", "").strip()
                summary = entry.get("summary", entry.get("description", ""))[:600].strip()
                text    = (title + " " + summary).lower()

                if not any(kw.lower() in text for kw in KEYWORDS):
                    seen.add(uid)
                    continue

                published = entry.get("published_parsed")
                if published:
                    pub_dt = datetime(*published[:6], tzinfo=timezone.utc)
                    if pub_dt < cutoff:
                        seen.add(uid)
                        continue

                articles.append({
                    "uid":     uid,
                    "title":   title,
                    "url":     url,
                    "summary": summary,
                    "source":  feed.feed.get("title", "Unknown Source"),
                })
                seen.add(uid)

                if len(articles) >= MAX_ARTICLES_PER_RUN:
                    break

        except Exception as e:
            log.error(f"Feed error ({feed_url}): {e}")

    save_seen(seen)
    log.info(f"Fetched {len(articles)} new relevant articles.")
    return articles


# ══════════════════════════════════════════════════════════════════════════════
#  AI SUMMARIES
# ══════════════════════════════════════════════════════════════════════════════
def ai_summarise(articles: list) -> str:
    if not articles:
        return "_No significant LNG news in the last 24 hours._"

    articles_text = "\n\n".join([
        f"SOURCE: {a['source']}\nTITLE: {a['title']}\nSUMMARY: {a['summary']}\nURL: {a['url']}"
        for a in articles[:20]
    ])

    prompt = f"""You are an expert LNG industry analyst preparing a concise morning briefing for a senior professional.

Below are today's LNG-related news articles. Your task:
1. Group them under these 4 categories (only include a category if there are relevant articles):
   - 📊 Market Prices & Trade Flows
   - 🌍 Policy & Geopolitics
   - 🏗️ Infrastructure & Terminals
   - 🏢 Company News & Deals

2. For each article write ONE sentence (max 30 words) capturing the key insight — not just the headline.
3. Add a "🔑 Key Takeaway" at the end: 2-3 sentences on the most strategically important development today.
4. Be direct. Skip filler phrases. Write like a Bloomberg brief.
5. Include the article URL as a plain link after each item.

Today's articles:
{articles_text}

Format each item as:
• [One-sentence insight] ([Source]) — URL

Keep the entire briefing under 600 words."""

    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        log.error(f"Claude API error: {e}")
        return "\n".join([f"• {a['title']} ({a['source']})\n  {a['url']}" for a in articles])


def ai_weekly_summary(articles: list) -> str:
    if not articles:
        return "_No significant LNG developments this week._"

    articles_text = "\n\n".join([
        f"DATE: {a.get('saved_at','')[:10]}\nSOURCE: {a['source']}\nTITLE: {a['title']}\nSUMMARY: {a['summary']}"
        for a in articles[:40]
    ])

    prompt = f"""You are a senior LNG industry analyst. Produce a weekly intelligence summary styled after a Wood Mackenzie weekly briefing.

This week's LNG articles:
{articles_text}

Structure your report:
1. 📊 **Week in Review** — 3-4 sentences on the dominant themes
2. 🔍 **Key Developments by Category** — group notable stories under Market, Policy, Infrastructure, Company
3. 📈 **Trend Watch** — what patterns or shifts are emerging across the week
4. ⚠️ **Risks & Opportunities** — 2-3 bullet points on what to watch next week

Be analytical, not just descriptive. Identify cause-and-effect. Keep under 500 words."""

    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        log.error(f"Claude weekly API error: {e}")
        return "_Weekly summary unavailable — Claude API error._"


def ai_monthly_summary(articles: list) -> str:
    if not articles:
        return "_No significant LNG developments this month._"

    articles_text = "\n\n".join([
        f"DATE: {a.get('saved_at','')[:10]}\nSOURCE: {a['source']}\nTITLE: {a['title']}\nSUMMARY: {a['summary']}"
        for a in articles[:60]
    ])

    month_name = datetime.now(SGT).strftime("%B %Y")

    prompt = f"""You are a senior LNG industry analyst. Produce a monthly strategic intelligence report for {month_name}, styled after an S&P Global Platts or Wood Mackenzie research note.

This month's LNG coverage:
{articles_text}

Structure your report:
1. 🗓️ **Executive Summary** — 4-5 sentences: what defined this month in LNG
2. 📊 **Market & Pricing** — key price movements, trade flow shifts, supply/demand dynamics
3. 🌍 **Geopolitical & Policy Landscape** — regulatory changes, sanctions, government actions
4. 🏗️ **Infrastructure & Projects** — FIDs, construction updates, new terminals, delays
5. 🏢 **Corporate Activity** — M&A, contracts, earnings highlights
6. 🔭 **Outlook for Next Month** — what developments to watch, upcoming catalysts
7. ⭐ **Analyst's Pick** — the single most strategically significant development this month and why

Write with authority. Be specific. Keep under 700 words."""

    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        log.error(f"Claude monthly API error: {e}")
        return "_Monthly report unavailable — Claude API error._"


# ══════════════════════════════════════════════════════════════════════════════
#  TELEGRAM
# ══════════════════════════════════════════════════════════════════════════════
def send_telegram(message: str):
    url    = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]

    for i, chunk in enumerate(chunks):
        payload = {
            "chat_id":                  TELEGRAM_CHAT_ID,
            "text":                     chunk,
            "parse_mode":               "Markdown",
            "disable_web_page_preview": True,
        }
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            log.info(f"Telegram chunk {i+1}/{len(chunks)} sent ✅")
        else:
            log.error(f"Telegram error: {resp.status_code} {resp.text}")
        time.sleep(0.5)


# ══════════════════════════════════════════════════════════════════════════════
#  JOB RUNNERS
# ══════════════════════════════════════════════════════════════════════════════
def run_digest():
    log.info("═══ Running LNG Morning Digest ═══")
    articles = fetch_articles(hours=26)

    if not articles:
        send_telegram(
            f"🛢️ *LNG Morning Briefing*\n"
            f"📅 {datetime.now(SGT).strftime('%A, %d %B %Y')}\n\n"
            f"_No significant new LNG developments in the last 24 hours._"
        )
        return

    save_to_history(articles)
    log.info("Generating AI summary…")
    summary  = ai_summarise(articles)
    date_str = datetime.now(SGT).strftime("%A, %d %B %Y")
    message  = (
        f"🛢️ *LNG Morning Intelligence Briefing*\n"
        f"📅 {date_str}\n"
        f"📰 {len(articles)} articles reviewed\n"
        f"{'─' * 30}\n\n"
        f"{summary}\n\n"
        f"{'─' * 30}\n"
        f"_Powered by Claude AI • Sources: Reuters, LNG Prime, OilPrice & more_"
    )
    send_telegram(message)
    log.info("Digest sent ✅")


def run_weekly_summary():
    log.info("═══ Running Weekly LNG Summary ═══")
    history = load_history()
    cutoff  = datetime.now(SGT) - timedelta(days=7)
    week_articles = [
        a for a in history
        if datetime.fromisoformat(a.get("saved_at", "2000-01-01")) > cutoff
    ]
    log.info(f"Weekly summary: {len(week_articles)} articles from last 7 days")
    summary  = ai_weekly_summary(week_articles)
    week_str = datetime.now(SGT).strftime("w/e %d %B %Y")
    message  = (
        f"📋 *LNG Weekly Intelligence Summary*\n"
        f"📅 {week_str}\n"
        f"📰 {len(week_articles)} articles analysed\n"
        f"{'─' * 30}\n\n"
        f"{summary}\n\n"
        f"{'─' * 30}\n"
        f"_Powered by Claude AI • LNG Intelligence Pipeline_"
    )
    send_telegram(message)
    log.info("Weekly summary sent ✅")


def run_monthly_summary():
    log.info("═══ Running Monthly LNG Report ═══")
    history = load_history()
    cutoff  = datetime.now(SGT) - timedelta(days=31)
    month_articles = [
        a for a in history
        if datetime.fromisoformat(a.get("saved_at", "2000-01-01")) > cutoff
    ]
    log.info(f"Monthly report: {len(month_articles)} articles from last 31 days")
    summary   = ai_monthly_summary(month_articles)
    month_str = datetime.now(SGT).strftime("%B %Y")
    message   = (
        f"📊 *LNG Monthly Strategic Intelligence Report*\n"
        f"📅 {month_str}\n"
        f"📰 {len(month_articles)} articles analysed\n"
        f"{'─' * 30}\n\n"
        f"{summary}\n\n"
        f"{'─' * 30}\n"
        f"_Powered by Claude AI • LNG Intelligence Pipeline_"
    )
    send_telegram(message)
    log.info("Monthly report sent ✅")


# ══════════════════════════════════════════════════════════════════════════════
#  SCHEDULER LOOP  (timezone-aware, no external scheduler library needed)
# ══════════════════════════════════════════════════════════════════════════════
def should_run(hour: int, minute: int) -> bool:
    now = datetime.now(SGT)
    return now.hour == hour and now.minute == minute


def main():
    log.info("🚀 LNG Intelligence Pipeline starting…")
    log.info(f"   Daily digest  : {DAILY_HOUR:02d}:{DAILY_MINUTE:02d} SGT")
    log.info(f"   Weekly summary: Monday {WEEKLY_HOUR:02d}:{WEEKLY_MINUTE:02d} SGT")
    log.info(f"   Monthly report: 1st of month {MONTHLY_HOUR:02d}:{MONTHLY_MINUTE:02d} SGT")

    # Run once on startup to confirm everything works
    log.info("Running startup test digest…")
    run_digest()

    last_daily   = None
    last_weekly  = None
    last_monthly = None

    while True:
        now_sgt = datetime.now(SGT)
        today   = now_sgt.date()

        # Daily at 07:00 SGT
        if should_run(DAILY_HOUR, DAILY_MINUTE) and last_daily != today:
            last_daily = today
            run_digest()

        # Weekly: Monday at 07:30 SGT
        if (now_sgt.weekday() == 0
                and should_run(WEEKLY_HOUR, WEEKLY_MINUTE)
                and last_weekly != today):
            last_weekly = today
            run_weekly_summary()

        # Monthly: 1st of month at 08:00 SGT
        if (now_sgt.day == 1
                and should_run(MONTHLY_HOUR, MONTHLY_MINUTE)
                and last_monthly != today):
            last_monthly = today
            run_monthly_summary()

        time.sleep(30)  # check every 30s — lightweight, never misses a window


if __name__ == "__main__":
    main()

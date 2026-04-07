#!/usr/bin/env python3
"""
LNG Intelligence Pipeline — Daily Digest
==========================================
Fetches RSS feeds, filters by LNG keywords, summarizes with Claude AI,
and delivers formatted briefings to Telegram.

Deployment: Railway.app (GitHub-connected, always-on Python service)
Timezone:   Singapore (SGT, UTC+8)
Schedule:   8:00 AM, 12:00 PM, 7:00 PM SGT

Setup:
  pip install feedparser requests anthropic

Run locally:
  python lng_digest.py              # starts polling loop
  python lng_digest.py --test       # sends one digest immediately, then exits
  python lng_digest.py --diagnose   # tests all feeds and prints diagnostics
"""

import os
import sys
import io
import json
import hashlib
import logging
import time
import argparse
from datetime import datetime, timezone, timedelta

import feedparser
import requests
import anthropic

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIGURATION (env vars for Railway, fallback to digest_config.py)
# ══════════════════════════════════════════════════════════════════════════════

# --- Credentials (env vars take priority, digest_config.py as fallback) ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")
ANTHROPIC_API_KEY   = os.environ.get("ANTHROPIC_API_KEY", "")

# Multi-recipient support: list of (chat_id, display_name) tuples
# Built from env vars — add COLLEAGUE_TELEGRAM_CHAT_ID, COLLEAGUE_2_TELEGRAM_CHAT_ID etc.
TELEGRAM_RECIPIENTS = None  # Will be populated below

# Fall back to digest_config.py if env vars are empty
try:
    import digest_config as _cfg
    TELEGRAM_BOT_TOKEN = TELEGRAM_BOT_TOKEN or getattr(_cfg, "TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID   = TELEGRAM_CHAT_ID or getattr(_cfg, "TELEGRAM_CHAT_ID", "")
    ANTHROPIC_API_KEY   = ANTHROPIC_API_KEY or getattr(_cfg, "ANTHROPIC_API_KEY", "")
    # If digest_config defines TELEGRAM_RECIPIENTS, use it directly
    TELEGRAM_RECIPIENTS = getattr(_cfg, "TELEGRAM_RECIPIENTS", None)
except ImportError:
    pass

# Build recipients list if not already set by digest_config
if not TELEGRAM_RECIPIENTS:
    TELEGRAM_RECIPIENTS = []
    # Primary recipient (you)
    if TELEGRAM_CHAT_ID:
        TELEGRAM_RECIPIENTS.append((TELEGRAM_CHAT_ID, "Primary"))
    # Additional recipients from env vars (COLLEAGUE_TELEGRAM_CHAT_ID, COLLEAGUE_2_...)
    for key, val in os.environ.items():
        if key.endswith("_TELEGRAM_CHAT_ID") and key != "TELEGRAM_CHAT_ID":
            name = key.replace("_TELEGRAM_CHAT_ID", "").replace("_", " ").title()
            TELEGRAM_RECIPIENTS.append((val, name))

# --- Timezone ---
SGT = timezone(timedelta(hours=8))

# --- Schedule: (hour, minute) tuples in SGT ---
DAILY_TIMES = [(8, 0), (12, 0), (19, 0)]

# --- Files ---
SEEN_FILE = "seen_articles.json"
HISTORY_FILE = "article_history.json"
LOG_FILE  = "lng_digest.log"

# --- Limits ---
MAX_ARTICLES_PER_RUN   = 30
ARTICLE_MAX_AGE_HOURS  = 48
SKIP_UNDATED_ARTICLES  = True

# --- Claude ---
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# ══════════════════════════════════════════════════════════════════════════════
#  RSS FEEDS — verified, working sources (Apr 2025)
# ══════════════════════════════════════════════════════════════════════════════
RSS_FEEDS = [
    # --- Major Wire Services & News ---
    "https://news.google.com/rss/search?q=LNG+liquefied+natural+gas&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=LNG+terminal+OR+LNG+cargo+OR+LNG+shipment&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=natural+gas+price+spot+market&hl=en&gl=US&ceid=US:en",

    # --- Energy-Specific Sources ---
    "https://oilprice.com/rss/main",
    "https://www.rigzone.com/news/rss/rigzone_latest.aspx",
    "https://www.offshore-energy.biz/feed/",
    "https://www.upstreamonline.com/rss",
    "https://www.spglobal.com/commodityinsights/en/rss-feed/natural-gas",
    "https://www.naturalgasintel.com/feed/",
    "https://www.hellenicshippingnews.com/category/lng/feed/",
    "https://splash247.com/feed/",

    # --- General Energy & Geopolitics ---
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/Energy.xml",

    # --- Industry Bodies ---
    "https://www.eia.gov/rss/todayinenergy.xml",
]

# ══════════════════════════════════════════════════════════════════════════════
#  KEYWORDS — terms that indicate LNG relevance
# ══════════════════════════════════════════════════════════════════════════════
KEYWORDS = [
    "lng", "liquefied natural gas", "natural gas",
    "henry hub", "ttf", "jkm", "nbp",
    "regasification", "liquefaction", "fsru", "flng",
    "gas terminal", "gas pipeline", "gas export", "gas import",
    "gas cargo", "gas shipment", "gas tanker",
    "gas price", "gas spot", "gas market", "gas trade",
    "gas supply", "gas demand",
    "cheniere", "venture global", "sempra", "tellurian", "driftwood",
    "qatar energy", "qatargas", "novatek", "yamal", "arctic lng",
    "santos", "woodside", "petronas lng", "shell lng", "totalenergies lng",
    "bp lng", "equinor lng", "eni lng", "chevron lng", "conocophillips lng",
    "sabine pass", "freeport lng", "cameron lng", "corpus christi",
    "golden pass", "port arthur lng", "plaquemines",
    "energy security", "gas sanctions", "energy transition",
]

# ══════════════════════════════════════════════════════════════════════════════
#  CATEGORIES — for AI-driven grouping
# ══════════════════════════════════════════════════════════════════════════════
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
#  LOGGING
# ══════════════════════════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(stream=io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")),
    ],
)
log = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
#  CLAUDE CLIENT
# ══════════════════════════════════════════════════════════════════════════════
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


# ══════════════════════════════════════════════════════════════════════════════
#  SEEN ARTICLES (deduplication)
# ══════════════════════════════════════════════════════════════════════════════
def load_seen() -> set:
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_seen(seen: set):
    # Keep only last 5000 hashes to prevent file bloat
    trimmed = list(seen)[-5000:]
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(trimmed, f)


# ══════════════════════════════════════════════════════════════════════════════
#  ARTICLE HISTORY (for weekly/monthly summaries)
# ══════════════════════════════════════════════════════════════════════════════
def save_to_history(articles: list[dict]):
    """Append articles to history file for weekly/monthly summary generation."""
    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, encoding="utf-8") as f:
            try:
                history = json.load(f)
            except json.JSONDecodeError:
                history = []

    for a in articles:
        history.append({
            "title":   a["title"],
            "url":     a["url"],
            "summary": a["summary"],
            "source":  a["source"],
            "date":    datetime.now(SGT).isoformat(),
        })

    # Keep last 30 days of history
    cutoff = (datetime.now(SGT) - timedelta(days=30)).isoformat()
    history = [h for h in history if h.get("date", "") >= cutoff]

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)
    log.info(f"Saved {len(articles)} articles to history ({len(history)} total)")


# ══════════════════════════════════════════════════════════════════════════════
#  FETCH & FILTER ARTICLES
# ══════════════════════════════════════════════════════════════════════════════
def parse_pub_date(entry) -> datetime | None:
    """Safely parse an RSS entry's publish date as UTC-aware datetime."""
    published = entry.get("published_parsed")
    if not published:
        return None
    try:
        # published_parsed is a time.struct_time; treat as UTC
        return datetime(*published[:6], tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def fetch_articles() -> list[dict]:
    seen     = load_seen()
    articles = []
    cutoff   = datetime.now(timezone.utc) - timedelta(hours=ARTICLE_MAX_AGE_HOURS)

    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            feed_name = feed.feed.get("title", feed_url[:50])

            if not feed.entries:
                log.warning(f"No entries: {feed_url[:60]}")
                continue

            for entry in feed.entries[:15]:
                url = entry.get("link", "")
                uid = hashlib.md5(url.encode()).hexdigest()
                if uid in seen:
                    continue

                title   = entry.get("title", "").strip()
                summary = entry.get("summary", entry.get("description", ""))[:600].strip()
                text    = (title + " " + summary).lower()

                # Must match at least one LNG keyword
                if not any(kw.lower() in text for kw in KEYWORDS):
                    seen.add(uid)
                    continue

                # Parse & check publish date (timezone-safe)
                pub_dt = parse_pub_date(entry)
                if pub_dt:
                    if pub_dt < cutoff:
                        seen.add(uid)
                        continue
                elif SKIP_UNDATED_ARTICLES:
                    seen.add(uid)
                    continue

                articles.append({
                    "uid":     uid,
                    "title":   title,
                    "url":     url,
                    "summary": summary,
                    "source":  feed_name,
                })
                seen.add(uid)

                if len(articles) >= MAX_ARTICLES_PER_RUN:
                    break

        except Exception as e:
            log.error(f"Feed error ({feed_url[:60]}): {e}")

    save_seen(seen)
    log.info(f"Fetched {len(articles)} new relevant articles")
    return articles


# ══════════════════════════════════════════════════════════════════════════════
#  AI SUMMARY VIA CLAUDE
# ══════════════════════════════════════════════════════════════════════════════
def ai_summarise(articles: list[dict]) -> str:
    """Ask Claude to produce a concise executive briefing from the articles."""
    if not articles:
        return "_No significant LNG news in the last 24 hours._"

    articles_text = "\n\n".join([
        f"SOURCE: {a['source']}\n"
        f"TITLE: {a['title']}\n"
        f"SUMMARY: {a['summary']}\n"
        f"URL: {a['url']}"
        for a in articles[:20]
    ])

    prompt = f"""You are an expert LNG industry analyst preparing a concise intelligence briefing for a senior professional.

Below are the latest LNG-related news articles. Your task:

1. Group them under these 4 categories (only include a category if there are relevant articles):
   - 📊 Market Prices & Trade Flows
   - 🌍 Policy & Geopolitics
   - 🏗️ Infrastructure & Terminals
   - 🏢 Company News & Deals

2. For each article write ONE sentence (max 30 words) capturing the key insight — not just the headline.
3. Add a "🔑 Key Takeaway" at the end: 2-3 sentences on the most strategically important development.
4. Be direct. Skip filler phrases. Write like a Bloomberg terminal brief.
5. Include the article URL as a plain link after each item.

Today's articles:
{articles_text}

Format each item as:
• [One-sentence insight] ([Source]) — URL

Keep the entire briefing under 600 words."""

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        log.error(f"Claude API error: {e}")
        # Fallback: simple formatted list
        return "\n".join([f"• {a['title']} ({a['source']})\n  {a['url']}" for a in articles])


# ══════════════════════════════════════════════════════════════════════════════
#  FORMAT TELEGRAM MESSAGE
# ══════════════════════════════════════════════════════════════════════════════
def format_message(summary: str, article_count: int, time_label: str = "") -> str:
    now = datetime.now(SGT)
    date_str = now.strftime("%A, %d %B %Y")
    time_str = time_label or now.strftime("%I:%M %p SGT")

    header = (
        f"🛢️ *LNG Intelligence Briefing*\n"
        f"📅 {date_str} • {time_str}\n"
        f"📰 {article_count} articles reviewed\n"
        f"{'─' * 30}\n\n"
    )

    footer = (
        f"\n\n{'─' * 30}\n"
        f"_Powered by Claude AI • {len(RSS_FEEDS)} sources_\n"
        f"_Updated 3× daily • Singapore Time (SGT)_"
    )

    return header + summary + footer


# ══════════════════════════════════════════════════════════════════════════════
#  SEND TO TELEGRAM
# ══════════════════════════════════════════════════════════════════════════════
def _send_to_chat(chat_id: str, message: str, recipient_name: str = ""):
    """Send message to a single Telegram chat, splitting if over 4096 char limit."""
    label = f"{recipient_name} ({chat_id})" if recipient_name else chat_id
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    chunks = [message[i:i + 4000] for i in range(0, len(message), 4000)]

    for i, chunk in enumerate(chunks):
        payload = {
            "chat_id":    chat_id,
            "text":       chunk,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }
        try:
            resp = requests.post(url, json=payload, timeout=15)
            if resp.status_code == 200:
                log.info(f"→ {label} chunk {i + 1}/{len(chunks)} sent ✅")
            else:
                log.error(f"→ {label} error: {resp.status_code} — {resp.text}")
                # Retry without Markdown if parsing failed
                if "can't parse entities" in resp.text.lower():
                    payload["parse_mode"] = ""
                    resp2 = requests.post(url, json=payload, timeout=15)
                    if resp2.status_code == 200:
                        log.info(f"→ {label} chunk {i + 1} sent (plain text fallback) ✅")
                    else:
                        log.error(f"→ {label} plain-text fallback also failed: {resp2.text}")
        except Exception as e:
            log.error(f"→ {label} send error: {e}")
        time.sleep(0.5)


def send_telegram(message: str):
    """Send message to all configured recipients."""
    if not TELEGRAM_RECIPIENTS:
        log.error("No recipients configured! Set TELEGRAM_CHAT_ID or TELEGRAM_RECIPIENTS.")
        return

    log.info(f"Sending to {len(TELEGRAM_RECIPIENTS)} recipient(s)…")
    success = 0
    for chat_id, name in TELEGRAM_RECIPIENTS:
        if not chat_id:
            log.warning(f"⚠ Skipping {name}: no chat_id configured")
            continue
        _send_to_chat(chat_id, message, name)
        success += 1

    log.info(f"✓ Sent to {success}/{len(TELEGRAM_RECIPIENTS)} recipients")


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN DIGEST JOB
# ══════════════════════════════════════════════════════════════════════════════
def run_digest(time_label: str = ""):
    log.info("═══ Running LNG Digest ═══")
    articles = fetch_articles()

    if not articles:
        message = (
            f"🛢️ *LNG Intelligence Briefing*\n"
            f"📅 {datetime.now(SGT).strftime('%A, %d %B %Y')}\n\n"
            f"_No significant new LNG developments since last update._"
        )
        send_telegram(message)
        log.info("No articles — short message sent")
        return

    # Save to history for weekly/monthly summaries
    save_to_history(articles)

    log.info(f"Generating AI summary for {len(articles)} articles…")
    summary = ai_summarise(articles)
    message = format_message(summary, len(articles), time_label)
    send_telegram(message)
    log.info("Digest complete ✅")


# ══════════════════════════════════════════════════════════════════════════════
#  FEED DIAGNOSTICS (--diagnose flag)
# ══════════════════════════════════════════════════════════════════════════════
def run_diagnostics():
    """Test all feeds and report which ones are returning articles."""
    print("=" * 70)
    print("FEED DIAGNOSTICS")
    print(f"Testing {len(RSS_FEEDS)} feeds")
    print(f"Article max age: {ARTICLE_MAX_AGE_HOURS} hours")
    print(f"Skip undated: {SKIP_UNDATED_ARTICLES}")
    print("=" * 70)

    total_entries = 0
    total_matched = 0
    working_feeds = 0

    for feed_url in RSS_FEEDS:
        print(f"\n→ {feed_url[:70]}")
        try:
            feed = feedparser.parse(feed_url)
            entries = feed.entries
            if not entries:
                print("   ✗ No entries")
                continue

            working_feeds += 1
            matched = 0
            for entry in entries[:10]:
                total_entries += 1
                title   = entry.get("title", "")
                summary = entry.get("summary", "")[:300]
                text    = (title + " " + summary).lower()

                if any(kw.lower() in text for kw in KEYWORDS):
                    matched += 1
                    total_matched += 1

                # Test date parsing
                pub_dt = parse_pub_date(entry)
                date_status = pub_dt.strftime("%Y-%m-%d %H:%M UTC") if pub_dt else "no date"
                if matched <= 2 and any(kw.lower() in text for kw in KEYWORDS):
                    print(f"   ✓ [{date_status}] {title[:60]}")

            print(f"   {len(entries)} entries, {matched} LNG matches")

        except Exception as e:
            print(f"   ✗ Error: {e}")

    print("\n" + "=" * 70)
    print(f"Working feeds:  {working_feeds}/{len(RSS_FEEDS)}")
    print(f"Total entries:  {total_entries}")
    print(f"LNG matches:    {total_matched}")
    print("=" * 70)


# ══════════════════════════════════════════════════════════════════════════════
#  SCHEDULER — polling loop for Railway (no cron needed)
# ══════════════════════════════════════════════════════════════════════════════
def start_scheduler():
    """Continuous polling loop. Checks scheduled times in SGT."""
    last_run_times = set()

    log.info("🟢 LNG Digest service started")
    log.info(f"   Timezone: SGT (UTC+8)")
    log.info(f"   Schedule: {', '.join(f'{h}:{m:02d}' for h, m in DAILY_TIMES)} SGT")
    log.info(f"   Feeds: {len(RSS_FEEDS)}")
    log.info(f"   Recipients: {[name for _, name in TELEGRAM_RECIPIENTS]}")
    log.info("")

    while True:
        try:
            now = datetime.now(SGT)

            for target_hour, target_minute in DAILY_TIMES:
                time_match = (
                    now.hour == target_hour
                    and abs(now.minute - target_minute) <= 2
                )
                run_key = (target_hour, target_minute, now.date())

                if time_match and run_key not in last_run_times:
                    last_run_times.add(run_key)
                    time_label = f"{target_hour}:{target_minute:02d} SGT"
                    log.info(f"⏰ Scheduled run: {time_label}")
                    run_digest(time_label)

            # Clean old run keys (keep only today)
            today = now.date()
            last_run_times = {k for k in last_run_times if k[2] == today}

            time.sleep(30)

        except KeyboardInterrupt:
            log.info("🛑 Service stopped by user")
            break
        except Exception as e:
            log.error(f"Unexpected error in scheduler: {e}", exc_info=True)
            time.sleep(60)


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LNG Intelligence Pipeline")
    parser.add_argument("--test", action="store_true", help="Send one digest now and exit")
    parser.add_argument("--diagnose", action="store_true", help="Test all feeds and exit")
    args = parser.parse_args()

    if args.diagnose:
        run_diagnostics()
    elif args.test:
        log.info("Running test digest…")
        run_digest("Test Run")
    else:
        start_scheduler()

#!/usr/bin/env python3
"""
LNG Intelligence Pipeline — Daily Digest
==========================================
Fetches RSS feeds, filters by LNG keywords, summarizes with Claude AI,
and delivers formatted briefings to Telegram.

Deployment: Railway.app (GitHub-connected, always-on Python service)
Timezone:   Singapore (SGT, UTC+8)
Schedule:   Configurable in digest_config.py

Usage:
  python lng_digest.py              # start polling loop (production)
  python lng_digest.py --test       # send one digest immediately, then exit
  python lng_digest.py --diagnose   # test all feeds and print diagnostics
"""

import os
import sys
import io
import re
import json
import base64
import hashlib
import logging
import time
import argparse
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, parse_qs

import feedparser
import requests
import anthropic

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIGURATION — loaded from digest_config.py, with safe defaults
# ══════════════════════════════════════════════════════════════════════════════

_has_config = False
try:
    import digest_config as _cfg
    _has_config = True
except ImportError:
    pass


def _conf(name, default=None):
    """Read a setting from digest_config.py, falling back to default."""
    if _has_config:
        return getattr(_cfg, name, default)
    return default


# --- Credentials (env vars take priority) ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "") or _conf("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")
ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "") or _conf("ANTHROPIC_API_KEY", "")

# --- Recipients ---
TELEGRAM_RECIPIENTS = _conf("TELEGRAM_RECIPIENTS", None)
if not TELEGRAM_RECIPIENTS:
    TELEGRAM_RECIPIENTS = []
    if TELEGRAM_CHAT_ID:
        TELEGRAM_RECIPIENTS.append((TELEGRAM_CHAT_ID, "Primary"))
    for key, val in os.environ.items():
        if key.endswith("_TELEGRAM_CHAT_ID") and key != "TELEGRAM_CHAT_ID":
            name = key.replace("_TELEGRAM_CHAT_ID", "").replace("_", " ").title()
            TELEGRAM_RECIPIENTS.append((val, name))

# --- Timezone ---
SGT = timezone(timedelta(hours=8))

# --- Schedule ---
DAILY_TIMES = _conf("DAILY_TIMES", [(8, 0), (12, 0), (15, 0), (21, 25)])

# --- Files ---
SEEN_FILE    = "seen_articles.json"
HISTORY_FILE = "article_history.json"
LOG_FILE     = "lng_digest.log"

# --- Limits ---
MAX_ARTICLES_PER_RUN  = _conf("MAX_ARTICLES_PER_RUN", 30)
ARTICLE_MAX_AGE_HOURS = _conf("ARTICLE_MAX_AGE_HOURS", 48)
SKIP_UNDATED_ARTICLES = _conf("SKIP_UNDATED_ARTICLES", True)

# --- Claude ---
CLAUDE_MODEL = _conf("CLAUDE_MODEL", "claude-sonnet-4-20250514")

# --- Feeds, keywords, categories ---
RSS_FEEDS  = _conf("RSS_FEEDS", [])
KEYWORDS   = _conf("KEYWORDS", [])
CATEGORIES = _conf("CATEGORIES", {})

if not RSS_FEEDS:
    sys.exit("ERROR: No RSS_FEEDS configured. Check digest_config.py.")
if not KEYWORDS:
    sys.exit("ERROR: No KEYWORDS configured. Check digest_config.py.")


# ══════════════════════════════════════════════════════════════════════════════
#  LOGGING (timestamps in SGT to match Railway dashboard)
# ══════════════════════════════════════════════════════════════════════════════
class SGTFormatter(logging.Formatter):
    """Forces log timestamps to SGT (UTC+8) regardless of server timezone."""
    def formatTime(self, record, datefmt=None):
        utc_dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        sgt_dt = utc_dt.astimezone(SGT)
        if datefmt:
            return sgt_dt.strftime(datefmt)
        return sgt_dt.strftime("%Y-%m-%d %H:%M:%S SGT")

_fmt = SGTFormatter("%(asctime)s [%(levelname)s] %(message)s")
_file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
_file_handler.setFormatter(_fmt)
_stream_handler = logging.StreamHandler(stream=io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8"))
_stream_handler.setFormatter(_fmt)

logging.basicConfig(level=logging.INFO, handlers=[_file_handler, _stream_handler])
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
#  GOOGLE NEWS URL RESOLVER
# ══════════════════════════════════════════════════════════════════════════════
def _extract_url_from_entry(entry) -> str | None:
    """Try to extract the real article URL from RSS entry metadata.

    Google News RSS entries often embed the source URL in:
    1. The <source url="..."> element (feedparser exposes as source.href)
    2. An <a href="..."> inside the description/summary HTML
    """
    # Strategy 1: source element
    source = entry.get("source", {})
    if isinstance(source, dict):
        href = source.get("href", "")
        if href and "news.google.com" not in href:
            return href

    # Strategy 2: first <a href> in description HTML
    desc = entry.get("summary", entry.get("description", ""))
    match = re.search(r'<a[^>]+href="(https?://[^"]+)"', desc)
    if match:
        candidate = match.group(1)
        if "news.google.com" not in candidate:
            return candidate

    return None


def _decode_google_news_url(url: str) -> str | None:
    """Decode the Base64 payload in a Google News CBMi... URL.

    Google News encodes the real URL in a base64url blob after /articles/.
    The blob starts with 'CBMi' and contains the article URL as a
    length-prefixed string inside a protobuf-like structure.
    """
    # Extract the base64 segment from the URL path
    match = re.search(r"/articles/([A-Za-z0-9_-]+)", url)
    if not match:
        return None

    encoded = match.group(1)
    # Add padding if needed
    padding = 4 - len(encoded) % 4
    if padding != 4:
        encoded += "=" * padding

    try:
        raw = base64.urlsafe_b64decode(encoded)
    except Exception:
        return None

    # The decoded bytes contain the URL as a string.
    # Extract all plausible URLs from the raw bytes.
    try:
        text = raw.decode("utf-8", errors="ignore")
    except Exception:
        text = raw.decode("latin-1", errors="ignore")

    urls = re.findall(r"https?://[^\s\x00-\x1f\"'<>]+", text)
    for candidate in urls:
        if "news.google.com" not in candidate and "google.com" not in candidate:
            return candidate.rstrip(".,;)")

    return None


def resolve_google_news_url(url: str, entry=None) -> str:
    """Resolve a Google News redirect URL to the actual article URL.

    Uses multiple strategies in order of speed/reliability:
    1. Extract from RSS entry metadata (no network call)
    2. Decode from Base64 payload in URL (no network call)
    3. Follow HTTP redirects (slow, often fails due to JS redirect)
    Falls back to the original URL if all strategies fail.
    """
    if "news.google.com" not in url:
        return url

    # Strategy 1: RSS entry metadata
    if entry:
        result = _extract_url_from_entry(entry)
        if result:
            return result

    # Strategy 2: Base64 decode
    result = _decode_google_news_url(url)
    if result:
        return result

    # Strategy 3: HTTP redirect (last resort, often blocked by JS)
    try:
        resp = requests.head(url, allow_redirects=True, timeout=8,
                             headers={"User-Agent": "Mozilla/5.0"})
        if "news.google.com" not in resp.url:
            return resp.url
    except Exception:
        pass

    log.warning(f"Could not resolve Google News URL: {url[:80]}")
    return url


# ══════════════════════════════════════════════════════════════════════════════
#  FETCH & FILTER ARTICLES
# ══════════════════════════════════════════════════════════════════════════════
def parse_pub_date(entry) -> datetime | None:
    """Safely parse an RSS entry's publish date as UTC-aware datetime."""
    published = entry.get("published_parsed")
    if not published:
        return None
    try:
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
                raw_url = entry.get("link", "")
                uid = hashlib.md5(raw_url.encode()).hexdigest()
                if uid in seen:
                    continue

                title   = entry.get("title", "").strip()
                summary = entry.get("summary", entry.get("description", ""))[:600].strip()
                text    = (title + " " + summary).lower()

                if not any(kw.lower() in text for kw in KEYWORDS):
                    seen.add(uid)
                    continue

                pub_dt = parse_pub_date(entry)
                if pub_dt:
                    if pub_dt < cutoff:
                        seen.add(uid)
                        continue
                elif SKIP_UNDATED_ARTICLES:
                    seen.add(uid)
                    continue

                # Resolve Google News redirect URLs to actual article URLs
                url = resolve_google_news_url(raw_url, entry=entry)

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

    # Build category list from config
    cat_list = "\n".join(CATEGORIES.keys()) if CATEGORIES else (
        "📊 Market Prices & Trade Flows\n"
        "🌍 Policy & Geopolitics\n"
        "🏗️ Infrastructure & Terminals\n"
        "🏢 Company News & Deals"
    )

    prompt = f"""You are an elite LNG industry analyst at a top-tier commodities research house. You are preparing a concise morning intelligence briefing for a C-suite executive. Your writing style: Bloomberg terminal, Wood Mackenzie, S&P Global Platts. No filler. Every word earns its place.

STRICT RULES:
- Group articles under ONLY these category headers (skip any category with zero articles):

{cat_list}

- Under each header, list each article as a single bullet using EXACTLY this format:
  • [One sentence, max 25 words, stating the strategic insight — NOT the headline reworded] ([Source Name]) — URL

- After all categories, add:
  🔑 Key Takeaway
  [2-3 sentences identifying the single most strategically significant development and why it matters for LNG markets]

WRITING STYLE:
- Bloomberg brevity. No adjectives unless they carry data ("record-high" yes, "significant" no).
- Lead each bullet with the actor or subject, not "According to..."
- Quantify where possible: prices, volumes, percentages, timelines.
- No preamble, no sign-off, no "Here is your briefing" — start directly with the first category header.

Today's articles:
{articles_text}"""

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        log.error(f"Claude API error: {e}")
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
        f"_Updated {len(DAILY_TIMES)}× daily • Singapore Time (SGT)_"
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


def send_telegram(message: str, recipients: list = None):
    """Send message to specified recipients (defaults to TELEGRAM_RECIPIENTS)."""
    targets = recipients or TELEGRAM_RECIPIENTS
    if not targets:
        log.error("No recipients configured! Set TELEGRAM_CHAT_ID or TELEGRAM_RECIPIENTS.")
        return

    log.info(f"Sending to {len(targets)} recipient(s)…")
    success = 0
    for chat_id, name in targets:
        if not chat_id:
            log.warning(f"⚠ Skipping {name}: no chat_id configured")
            continue
        _send_to_chat(chat_id, message, name)
        success += 1

    log.info(f"✓ Sent to {success}/{len(targets)} recipients")


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
    # Import job scraper if available
    job_runner = None
    try:
        from lng_jobs import run_job_check
        JOB_TIMES = _conf("JOB_TIMES", [])
        if JOB_TIMES:
            job_runner = (run_job_check, JOB_TIMES)
            log.info(f"   Job scraper: {', '.join(f'{h}:{m:02d}' for h, m in JOB_TIMES)} SGT")
    except ImportError:
        pass

    last_run_times = set()

    log.info("🟢 LNG Digest service started")
    log.info(f"   Timezone: SGT (UTC+8)")
    log.info(f"   News schedule: {', '.join(f'{h}:{m:02d}' for h, m in DAILY_TIMES)} SGT")
    log.info(f"   Feeds: {len(RSS_FEEDS)}")
    log.info(f"   Recipients: {[name for _, name in TELEGRAM_RECIPIENTS]}")
    log.info("")

    while True:
        try:
            now = datetime.now(SGT)

            # --- News digest schedule ---
            for target_hour, target_minute in DAILY_TIMES:
                time_match = (
                    now.hour == target_hour
                    and abs(now.minute - target_minute) <= 2
                )
                run_key = ("news", target_hour, target_minute, now.date())

                if time_match and run_key not in last_run_times:
                    last_run_times.add(run_key)
                    time_label = f"{target_hour}:{target_minute:02d} SGT"
                    log.info(f"⏰ Scheduled news digest: {time_label}")
                    run_digest(time_label)

            # --- Job scraper schedule ---
            if job_runner:
                job_func, job_times = job_runner
                for target_hour, target_minute in job_times:
                    time_match = (
                        now.hour == target_hour
                        and abs(now.minute - target_minute) <= 2
                    )
                    run_key = ("jobs", target_hour, target_minute, now.date())

                    if time_match and run_key not in last_run_times:
                        last_run_times.add(run_key)
                        time_label = f"{target_hour}:{target_minute:02d} SGT"
                        log.info(f"⏰ Scheduled job check: {time_label}")
                        job_func()

            # Clean old run keys (keep only today)
            today = now.date()
            last_run_times = {k for k in last_run_times if k[-1] == today}

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
    parser.add_argument("--test-jobs", action="store_true", help="Run one job check and exit")
    args = parser.parse_args()

    if args.diagnose:
        run_diagnostics()
    elif args.test:
        log.info("Running test digest…")
        run_digest("Test Run")
    elif args.test_jobs:
        from lng_jobs import run_job_check
        log.info("Running test job check…")
        run_job_check()
    else:
        start_scheduler()

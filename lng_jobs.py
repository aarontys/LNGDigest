#!/usr/bin/env python3
"""
LNG Job Scraper
================
Polls job board RSS feeds for LNG-relevant postings, deduplicates against
a seen-jobs file, and sends new matches to Telegram.

Designed to run alongside lng_digest.py — the scheduler in lng_digest.py
calls run_job_check() at the times defined in digest_config.JOB_TIMES.

Can also run standalone:
  python lng_jobs.py              # run one check and exit
  python lng_jobs.py --diagnose   # test all job feeds and print diagnostics
"""

import os
import json
import hashlib
import logging
import argparse
from datetime import datetime, timezone, timedelta

import feedparser

# Import shared infrastructure from lng_digest
from lng_digest import (
    _conf, SGT, TELEGRAM_BOT_TOKEN, send_telegram, log,
    resolve_google_news_url,
)

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIGURATION — from digest_config.py
# ══════════════════════════════════════════════════════════════════════════════
JOB_FEEDS      = _conf("JOB_FEEDS", [])
JOB_KEYWORDS   = _conf("JOB_KEYWORDS", [])
JOB_TARGET_COS = _conf("JOB_TARGET_COMPANIES", [])
JOB_RECIPIENTS = _conf("JOB_RECIPIENTS", None)

SEEN_JOBS_FILE = "seen_jobs.json"

# Max age for job postings (days) — older postings are skipped
JOB_MAX_AGE_DAYS = 7


# ══════════════════════════════════════════════════════════════════════════════
#  SEEN JOBS (deduplication)
# ══════════════════════════════════════════════════════════════════════════════
def load_seen_jobs() -> set:
    if os.path.exists(SEEN_JOBS_FILE):
        with open(SEEN_JOBS_FILE, encoding="utf-8") as f:
            try:
                return set(json.load(f))
            except json.JSONDecodeError:
                return set()
    return set()


def save_seen_jobs(seen: set):
    trimmed = list(seen)[-3000:]
    with open(SEEN_JOBS_FILE, "w", encoding="utf-8") as f:
        json.dump(trimmed, f)


# ══════════════════════════════════════════════════════════════════════════════
#  FETCH & FILTER JOB POSTINGS
# ══════════════════════════════════════════════════════════════════════════════
def fetch_jobs() -> list[dict]:
    """Poll all job feeds, filter by keywords, return new matches."""
    if not JOB_FEEDS:
        log.warning("No JOB_FEEDS configured — skipping job check")
        return []

    seen = load_seen_jobs()
    jobs = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=JOB_MAX_AGE_DAYS)

    for feed_url in JOB_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            feed_name = feed.feed.get("title", feed_url[:50])

            if not feed.entries:
                log.info(f"Jobs — no entries: {feed_url[:60]}")
                continue

            for entry in feed.entries[:20]:
                raw_url = entry.get("link", "")
                uid   = hashlib.md5(raw_url.encode()).hexdigest()
                if uid in seen:
                    continue

                title   = entry.get("title", "").strip()
                summary = entry.get("summary", entry.get("description", ""))[:800].strip()
                company = entry.get("author", entry.get("source", {}).get("title", "")).strip()
                location = ""

                # Try to extract location from common fields
                for field in ["location", "georss_point", "geo_name"]:
                    if hasattr(entry, field):
                        location = str(getattr(entry, field, ""))
                        break

                text = (title + " " + summary + " " + company).lower()

                # Must match at least one job keyword
                if not any(kw.lower() in text for kw in JOB_KEYWORDS):
                    seen.add(uid)
                    continue

                # Check date if available
                pub_parsed = entry.get("published_parsed")
                if pub_parsed:
                    try:
                        pub_dt = datetime(*pub_parsed[:6], tzinfo=timezone.utc)
                        if pub_dt < cutoff:
                            seen.add(uid)
                            continue
                    except (ValueError, TypeError):
                        pass

                # Resolve Google News redirect URLs to actual article URLs
                url = resolve_google_news_url(raw_url, entry=entry)

                # Check if this is a target company
                is_target = any(tc.lower() in text for tc in JOB_TARGET_COS)

                jobs.append({
                    "uid":        uid,
                    "title":      title,
                    "url":        url,
                    "company":    company,
                    "location":   location,
                    "summary":    summary[:300],
                    "source":     feed_name,
                    "is_target":  is_target,
                })
                seen.add(uid)

        except Exception as e:
            log.error(f"Job feed error ({feed_url[:60]}): {e}")

    save_seen_jobs(seen)
    log.info(f"Found {len(jobs)} new job postings")
    return jobs


# ══════════════════════════════════════════════════════════════════════════════
#  FORMAT JOB ALERT MESSAGE
# ══════════════════════════════════════════════════════════════════════════════
def format_job_message(jobs: list[dict]) -> str:
    """Format job postings into a Telegram message."""
    now = datetime.now(SGT)
    date_str = now.strftime("%A, %d %B %Y")
    time_str = now.strftime("%I:%M %p SGT")

    header = (
        f"💼 *LNG Job Alert*\n"
        f"📅 {date_str} • {time_str}\n"
        f"🔍 {len(jobs)} new posting{'s' if len(jobs) != 1 else ''}\n"
        f"{'─' * 30}\n\n"
    )

    # Sort: target companies first, then alphabetical by title
    target_jobs = [j for j in jobs if j["is_target"]]
    other_jobs  = [j for j in jobs if not j["is_target"]]

    lines = []

    if target_jobs:
        lines.append("⭐ *Target Companies*\n")
        for j in target_jobs:
            company_str = f" — {j['company']}" if j['company'] else ""
            location_str = f" 📍 {j['location']}" if j['location'] else ""
            lines.append(
                f"• *{j['title']}*{company_str}{location_str}\n"
                f"  {j['url']}\n"
            )

    if other_jobs:
        if target_jobs:
            lines.append("\n📋 *Other Matches*\n")
        for j in other_jobs:
            company_str = f" — {j['company']}" if j['company'] else ""
            location_str = f" 📍 {j['location']}" if j['location'] else ""
            lines.append(
                f"• {j['title']}{company_str}{location_str}\n"
                f"  {j['url']}\n"
            )

    footer = (
        f"\n{'─' * 30}\n"
        f"_Checked {len(JOB_FEEDS)} job feeds • 2× daily_"
    )

    return header + "\n".join(lines) + footer


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN JOB CHECK
# ══════════════════════════════════════════════════════════════════════════════
def run_job_check():
    """Fetch new job postings and send alert if any found."""
    log.info("═══ Running Job Check ═══")
    jobs = fetch_jobs()

    if not jobs:
        log.info("No new job postings found")
        return

    message = format_job_message(jobs)
    send_telegram(message, recipients=JOB_RECIPIENTS)
    log.info(f"Job alert sent — {len(jobs)} postings ✅")


# ══════════════════════════════════════════════════════════════════════════════
#  DIAGNOSTICS
# ══════════════════════════════════════════════════════════════════════════════
def run_job_diagnostics():
    """Test all job feeds and report results."""
    print("=" * 70)
    print("JOB FEED DIAGNOSTICS")
    print(f"Testing {len(JOB_FEEDS)} feeds")
    print(f"Job keywords: {len(JOB_KEYWORDS)}")
    print(f"Target companies: {len(JOB_TARGET_COS)}")
    print("=" * 70)

    total_entries = 0
    total_matched = 0
    working_feeds = 0

    for feed_url in JOB_FEEDS:
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
                company = entry.get("author", "")
                text    = (title + " " + summary + " " + company).lower()

                if any(kw.lower() in text for kw in JOB_KEYWORDS):
                    matched += 1
                    total_matched += 1
                    is_target = any(tc.lower() in text for tc in JOB_TARGET_COS)
                    flag = " ⭐ TARGET" if is_target else ""
                    if matched <= 3:
                        print(f"   ✓ {title[:55]}{flag}")

            print(f"   {len(entries)} entries, {matched} keyword matches")

        except Exception as e:
            print(f"   ✗ Error: {e}")

    print("\n" + "=" * 70)
    print(f"Working feeds:  {working_feeds}/{len(JOB_FEEDS)}")
    print(f"Total entries:  {total_entries}")
    print(f"Keyword matches: {total_matched}")
    print("=" * 70)


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT (standalone usage)
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LNG Job Scraper")
    parser.add_argument("--diagnose", action="store_true", help="Test all job feeds and exit")
    args = parser.parse_args()

    if args.diagnose:
        run_job_diagnostics()
    else:
        run_job_check()

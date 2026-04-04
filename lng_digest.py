#!/usr/bin/env python3
"""
LNG Intelligence Pipeline - Daily Digest
Fetches RSS feeds, filters by LNG keywords, summarizes with Claude AI,
and delivers to multiple Telegram recipients at 3 fixed times daily.

Deployment: Railway.app (GitHub-connected Python service)
Timezone: Singapore (SGT, UTC+8)
Schedule: 8:00 AM, 12:00 PM, 7:00 PM SGT
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
import time
import re
import hashlib

import feedparser
import requests
from anthropic import Anthropic

from digest_config import (
    TELEGRAM_RECIPIENTS,
    TELEGRAM_BOT_TOKEN,
    DAILY_TIMES,
    TIMEZONE,
    RSS_FEEDS,
    LNG_KEYWORDS,
    ARTICLE_MAX_AGE_HOURS,
    SKIP_UNDATED_ARTICLES,
    ANTHROPIC_API_KEY,
    CLAUDE_MODEL,
    DIGEST_CATEGORIES,
    SEEN_ARTICLES_FILE,
    LOG_FILE,
    LOG_LEVEL,
    LOG_FORMAT,
)

# ==============================================================================
# LOGGING SETUP
# ==============================================================================
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# ==============================================================================
# TELEGRAM SERVICE
# ==============================================================================
class TelegramService:
    """Handles sending messages to multiple Telegram recipients."""
    
    def __init__(self, bot_token):
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
    
    def send_message(self, text, chat_id, parse_mode="HTML"):
        """
        Send formatted message to a recipient.
        
        Args:
            text: Message content (HTML-formatted)
            chat_id: Telegram chat ID
            parse_mode: "HTML" or "Markdown"
        
        Returns:
            bool: True if sent successfully, False otherwise
        """
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": False,
            }
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"✓ Message sent to {chat_id}")
                return True
            else:
                logger.error(f"✗ Failed to send to {chat_id}: {response.text}")
                return False
        except Exception as e:
            logger.error(f"✗ Telegram error for {chat_id}: {str(e)}")
            return False
    
    def send_to_all_recipients(self, text, recipients):
        """
        Send message to all configured recipients.
        
        Args:
            text: Message content
            recipients: List of (chat_id, recipient_name) tuples
        
        Returns:
            dict: Results per recipient
        """
        results = {}
        for chat_id, recipient_name in recipients:
            if not chat_id:
                logger.warning(f"⚠ Skipping {recipient_name}: no chat_id configured")
                results[recipient_name] = False
                continue
            
            logger.info(f"→ Sending to {recipient_name} ({chat_id})")
            success = self.send_message(text, chat_id)
            results[recipient_name] = success
            time.sleep(0.5)  # Rate limiting between sends
        
        return results

# ==============================================================================
# ARTICLE FETCHING & FILTERING
# ==============================================================================
class ArticleFetcher:
    """Fetches and filters articles from RSS feeds."""
    
    def __init__(self):
        self.seen_articles = self._load_seen_articles()
    
    def _load_seen_articles(self):
        """Load set of previously seen article hashes."""
        if os.path.exists(SEEN_ARTICLES_FILE):
            with open(SEEN_ARTICLES_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        return set()
    
    def _save_seen_articles(self):
        """Persist seen articles to disk."""
        with open(SEEN_ARTICLES_FILE, "w", encoding="utf-8") as f:
            json.dump(list(self.seen_articles), f, indent=2)
        logger.info(f"✓ Saved {len(self.seen_articles)} article hashes")
    
    def _hash_article(self, title, link):
        """Create deterministic hash for article deduplication."""
        content = f"{title}|{link}".encode("utf-8")
        return hashlib.md5(content).hexdigest()
    
    def _is_recent(self, pub_date):
        """Check if article is within max age threshold."""
        if not pub_date:
            return not SKIP_UNDATED_ARTICLES
        
        try:
            article_time = datetime(*pub_date[:6])
        except (ValueError, TypeError):
            return not SKIP_UNDATED_ARTICLES
        
        age = datetime.utcnow() - article_time
        return age.total_seconds() < (ARTICLE_MAX_AGE_HOURS * 3600)
    
    def _is_lng_relevant(self, title, summary):
        """Check if article matches LNG keywords."""
        text = f"{title} {summary}".lower()
        return any(keyword.lower() in text for keyword in LNG_KEYWORDS)
    
    def fetch_articles(self):
        """
        Fetch and filter articles from all RSS feeds.
        
        Returns:
            list: Filtered article dicts with keys:
                  title, link, summary, pub_date, source_feed
        """
        articles = []
        
        logger.info(f"→ Fetching from {len(RSS_FEEDS)} feeds...")
        
        for feed_url in RSS_FEEDS:
            try:
                feed = feedparser.parse(feed_url)
                
                if feed.bozo:
                    logger.warning(f"⚠ Feed parse warning: {feed_url}")
                
                for entry in feed.entries[:10]:  # Limit per feed
                    title = entry.get("title", "No title")
                    link = entry.get("link", "")
                    summary = entry.get("summary", "")
                    pub_date = entry.get("published_parsed", None)
                    
                    # Deduplication
                    article_hash = self._hash_article(title, link)
                    if article_hash in self.seen_articles:
                        continue
                    
                    # Age filter
                    if not self._is_recent(pub_date):
                        continue
                    
                    # LNG relevance
                    if not self._is_lng_relevant(title, summary):
                        continue
                    
                    articles.append({
                        "title": title,
                        "link": link,
                        "summary": summary[:300],  # Truncate for API efficiency
                        "pub_date": pub_date,
                        "source_feed": feed.feed.get("title", feed_url),
                        "hash": article_hash,
                    })
                    
                    self.seen_articles.add(article_hash)
                
            except Exception as e:
                logger.error(f"✗ Error fetching {feed_url}: {str(e)}")
                continue
        
        self._save_seen_articles()
        logger.info(f"✓ Fetched and filtered {len(articles)} articles")
        
        return articles

# ==============================================================================
# CLAUDE SUMMARIZATION
# ==============================================================================
class DigestSummarizer:
    """Summarizes and categorizes articles using Claude AI."""
    
    def __init__(self, api_key):
        self.client = Anthropic(api_key=api_key)
    
    def summarize_articles(self, articles):
        """
        Summarize articles into predefined categories using Claude.
        
        Args:
            articles: List of article dicts
        
        Returns:
            dict: Categorized summaries
        """
        if not articles:
            return {}
        
        # Prepare article list for Claude
        article_text = "\n\n".join([
            f"Title: {a['title']}\n"
            f"Link: {a['link']}\n"
            f"Summary: {a['summary']}"
            for a in articles
        ])
        
        prompt = f"""Analyze the following LNG industry articles and categorize them into these 4 categories:
1. Market Prices & Trade Flows
2. Policy & Geopolitics
3. Infrastructure & Terminals
4. Company News & Deals

For each category, provide a 2-3 sentence summary highlighting key developments.
If no articles fit a category, skip it.

Articles:
{article_text}

Format your response EXACTLY as:
**Market Prices & Trade Flows**
[summary or "None today"]

**Policy & Geopolitics**
[summary or "None today"]

**Infrastructure & Terminals**
[summary or "None today"]

**Company News & Deals**
[summary or "None today"]
"""
        
        try:
            message = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=1000,
                messages=[
                    {"role": "user", "content": prompt}
                ],
            )
            
            response_text = message.content[0].text
            logger.info("✓ Claude summarization complete")
            
            return response_text
        
        except Exception as e:
            logger.error(f"✗ Claude API error: {str(e)}")
            return ""

# ==============================================================================
# DIGEST FORMATTING
# ==============================================================================
class DigestFormatter:
    """Formats digest for Telegram delivery."""
    
    @staticmethod
    def format_telegram_message(summary, article_count, send_time):
        """
        Format digest summary into Telegram HTML message.
        
        Args:
            summary: Claude's categorized summary
            article_count: Number of articles processed
            send_time: String timestamp (e.g., "8:00 AM")
        
        Returns:
            str: HTML-formatted Telegram message
        """
        now = datetime.now().strftime("%Y-%m-%d")
        
        header = f"""<b>🚀 LNG Intelligence Briefing</b>
<i>{now} | {send_time}</i>

<b>Articles Today:</b> {article_count}

"""
        
        if not summary or summary.strip() == "":
            body = "<i>No relevant LNG articles found.</i>"
        else:
            body = summary
        
        footer = f"""
<i>Updated 3x daily • Singapore Time (SGT, UTC+8)</i>
<i>Powered by Claude AI • {len(RSS_FEEDS)} feeds</i>"""
        
        message = header + body + footer
        
        # HTML escape special characters
        message = (message
                   .replace("&", "&amp;")
                   .replace("<", "&lt;")
                   .replace(">", "&gt;"))
        
        # Re-apply intentional HTML tags
        message = (message
                   .replace("&lt;b&gt;", "<b>")
                   .replace("&lt;/b&gt;", "</b>")
                   .replace("&lt;i&gt;", "<i>")
                   .replace("&lt;/i&gt;", "</i>"))
        
        return message

# ==============================================================================
# MAIN DIGEST LOGIC
# ==============================================================================
class LNGDigest:
    """Orchestrates the full digest pipeline."""
    
    def __init__(self):
        self.telegram = TelegramService(TELEGRAM_BOT_TOKEN)
        self.fetcher = ArticleFetcher()
        self.summarizer = DigestSummarizer(ANTHROPIC_API_KEY)
        self.formatter = DigestFormatter()
        self.last_run_times = set()
    
    def run_digest(self, send_time_str):
        """
        Execute full digest pipeline and send to all recipients.
        
        Args:
            send_time_str: String like "8:00 AM" for header
        """
        logger.info("=" * 70)
        logger.info(f"→ Digest run initiated at {datetime.now()}")
        logger.info("=" * 70)
        
        # Fetch & filter articles
        articles = self.fetcher.fetch_articles()
        
        if not articles:
            logger.info("⚠ No articles to process; skipping digest")
            return
        
        # Summarize with Claude
        summary = self.summarizer.summarize_articles(articles)
        
        # Format for Telegram
        message = self.formatter.format_telegram_message(
            summary,
            len(articles),
            send_time_str
        )
        
        # Send to all recipients
        logger.info(f"→ Sending to {len(TELEGRAM_RECIPIENTS)} recipient(s)...")
        results = self.telegram.send_to_all_recipients(message, TELEGRAM_RECIPIENTS)
        
        # Log results
        success_count = sum(1 for v in results.values() if v)
        logger.info(f"✓ Sent to {success_count}/{len(TELEGRAM_RECIPIENTS)} recipients")
        logger.info("=" * 70)
    
    def should_run(self, target_hour, target_minute):
        """
        Check if this is a scheduled run time (prevents duplicates).
        
        Args:
            target_hour: Hour (0-23, SGT)
            target_minute: Minute (0-59)
        
        Returns:
            bool: True if this run hasn't been done yet today
        """
        now = datetime.now()
        today = now.date()
        current_hour = now.hour
        current_minute = now.minute
        
        # Check if we're within 2 minutes of the scheduled time
        time_match = (current_hour == target_hour and 
                     abs(current_minute - target_minute) <= 2)
        
        if not time_match:
            return False
        
        # Prevent duplicate runs for the same (hour, minute, date)
        run_key = (target_hour, target_minute, today)
        if run_key in self.last_run_times:
            return False
        
        self.last_run_times.add(run_key)
        return True
    
    def start(self):
        """
        Start the digest service with continuous polling loop.
        Runs at 8 AM, 12 PM, and 7 PM SGT daily.
        """
        logger.info("🟢 LNG Digest service started")
        logger.info(f"   Recipients: {[name for _, name in TELEGRAM_RECIPIENTS]}")
        logger.info(f"   Schedule: {', '.join([f'{h}:{m:02d}' for h, m in DAILY_TIMES])} SGT")
        logger.info(f"   Feeds: {len(RSS_FEEDS)}")
        logger.info("")
        
        while True:
            try:
                now = datetime.now()
                
                # Check each scheduled time
                for target_hour, target_minute in DAILY_TIMES:
                    if self.should_run(target_hour, target_minute):
                        send_time_str = f"{target_hour}:{target_minute:02d} SGT"
                        self.run_digest(send_time_str)
                
                # Poll every 30 seconds to catch scheduled times
                time.sleep(30)
            
            except KeyboardInterrupt:
                logger.info("🛑 Service stopped by user")
                break
            except Exception as e:
                logger.error(f"✗ Unexpected error: {str(e)}")
                time.sleep(60)  # Brief pause before retry

# ==============================================================================
# ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    digest = LNGDigest()
    digest.start()

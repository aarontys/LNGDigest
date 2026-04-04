# ==============================================================================
# LNG Intelligence Pipeline Configuration
# Multi-recipient support with 3 daily send times (8 AM, 12 PM, 7 PM SGT)
# ==============================================================================

import os
from datetime import datetime

# ==============================================================================
# TELEGRAM RECIPIENTS - Option 3 Multi-Recipient Setup
# ==============================================================================
# Format: List of tuples (chat_id, recipient_name)
# chat_id can be retrieved from Telegram bot's message history or @userinfobot
# IMPORTANT: Keep these secure; prefer environment variables in production

TELEGRAM_RECIPIENTS = [
    (os.getenv("TELEGRAM_CHAT_ID"), "You"),  # Primary recipient
    # Uncomment and add colleague details when ready:
    (os.getenv("COLLEAGUE_TELEGRAM_CHAT_ID"), "Jennifer"),
]

# Fallback for single recipient (legacy support)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# ==============================================================================
# SCHEDULE CONFIGURATION
# ==============================================================================
# Three daily digest sends in Singapore Time (SGT, UTC+8)
DAILY_TIMES = [
    (8, 0),    # 8:00 AM SGT
    (12, 0),   # 12:00 PM SGT
    (19, 0),   # 7:00 PM SGT
]

TIMEZONE = "Asia/Singapore"

# ==============================================================================
# RSS FEEDS
# ==============================================================================
# Core LNG industry sources (~14 feeds covering markets, policy, infrastructure)
RSS_FEEDS = [
    # Energy & LNG Specialist
    "https://www.energy-pedia.com/feed/",
    "https://www.lngworld.com/feed/",
    "https://www.lngintel.com/feed/",
    
    # Major News Aggregators
    "https://feeds.reuters.com/energy/",
    "https://feeds.bloomberg.com/markets/energy.rss",
    
    # Geopolitics & Trade
    "https://feeds.ft.com/markets/energy",
    "https://www.aljazeera.com/xml/rss/all.xml",
    
    # Policy & Regulation
    "https://www.iea.org/feeds/",
    "https://www.igu.org/feeds/",
    
    # Infrastructure & Projects
    "https://www.osmre.gov/rss/",  # US mineral resources
    "https://www.oie.ru/en/rss/",  # Russian energy updates
    
    # Company News
    "https://investor.shell.com/rss/news.xml",
    "https://www.totalenergies.com/en/rss",
    "https://newsroom.equinor.com/feed/",
    "https://newsroom.bp.com/rss/releases.xml",
]

# ==============================================================================
# ARTICLE FILTERING
# ==============================================================================
# LNG relevance keywords (matched against article title and summary)
LNG_KEYWORDS = [
    "LNG", "liquefied natural gas", "liquefied gas",
    "natural gas market", "gas prices", "gas trade",
    "LNG terminal", "LNG export", "LNG import",
    "regasification", "gas carrier", "FSRU",
    "spot market", "long-term contract", "gas supply",
    "pipeline", "infrastructure", "geopolitics",
    "Russia gas", "Qatar LNG", "Australia LNG",
    "energy security", "energy transition",
]

# Maximum article age (hours from now)
ARTICLE_MAX_AGE_HOURS = 48

# Skip articles without publication date
SKIP_UNDATED_ARTICLES = True

# ==============================================================================
# CLAUDE API
# ==============================================================================
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = "claude-3-5-sonnet-20241022"

# Digest categorization prompt
DIGEST_CATEGORIES = [
    "Market Prices & Trade Flows",
    "Policy & Geopolitics",
    "Infrastructure & Terminals",
    "Company News & Deals",
]

# ==============================================================================
# FILE PATHS
# ==============================================================================
SEEN_ARTICLES_FILE = "seen_articles.json"
LOG_FILE = "lng_digest.log"

# ==============================================================================
# LOGGING
# ==============================================================================
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

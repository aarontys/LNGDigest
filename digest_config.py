"""
digest_config.py — Configuration for LNG Morning Digest
========================================================
Credentials are loaded from environment variables.
On Railway: set these in the Railway dashboard under Variables.
Locally: create a .env file (see .env.example).
"""

import os

# ── Telegram ───────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]

# ── Anthropic (Claude AI) ──────────────────────────────────────────────────────
ANTHROPIC_API_KEY  = os.environ["ANTHROPIC_API_KEY"]

# ── Feed Settings ──────────────────────────────────────────────────────────────
MAX_ARTICLES_PER_RUN = 30
SEEN_FILE            = "/data/seen_articles.json"   # persistent volume on Railway

# ── LNG Relevance Keywords ─────────────────────────────────────────────────────
KEYWORDS = [
    "LNG", "liquefied natural gas", "LNG terminal", "LNG tanker",
    "LNG export", "LNG import", "LNG price", "LNG cargo", "LNG carrier",
    "LNG regasification", "LNG liquefaction", "LNG bunkering", "FSRU",
    "natural gas market", "gas supply", "gas prices", "JKM", "TTF",
    "Henry Hub", "Sabine Pass", "Freeport LNG", "Qatar Energy",
    "Shell LNG", "TotalEnergies LNG", "BP gas",
]

# ── RSS Feeds ──────────────────────────────────────────────────────────────────
RSS_FEEDS = [
    # LNG-Specific
    "https://www.lngprime.com/feed/",
    "https://www.naturalgasintel.com/feed/",

    # Energy & Commodities
    "https://oilprice.com/rss/main",
    "https://energymonitor.ai/feed/",

    # Business & Markets
    "https://feeds.reuters.com/reuters/businessNews",
    "https://feeds.reuters.com/reuters/companyNews",

    # Geopolitics
    "https://feeds.reuters.com/Reuters/worldNews",

    # Infrastructure & Projects
    "https://www.offshore-energy.biz/feed/",
    "https://www.upstreamonline.com/rss",
]

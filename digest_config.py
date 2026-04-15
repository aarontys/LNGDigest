# ══════════════════════════════════════════════════════════════════════════════
#  LNG Intelligence Pipeline — Configuration
# ══════════════════════════════════════════════════════════════════════════════
#  Single source of truth for all settings. Credentials come from environment
#  variables (Railway dashboard → Variables). Everything else is edited here.
# ══════════════════════════════════════════════════════════════════════════════

import os

# ── Credentials (set in Railway environment variables) ────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY")

# ── Recipients ────────────────────────────────────────────────────────────────
# Format: (env_var_with_chat_id, display_name)
# Add colleagues by creating a new Railway env var and adding a line here.
TELEGRAM_RECIPIENTS = [
    (os.getenv("TELEGRAM_CHAT_ID"), "Aaron"),
    (os.getenv("COLLEAGUE_TELEGRAM_CHAT_ID"), "Jennifer"),
    # (os.getenv("COLLEAGUE_2_TELEGRAM_CHAT_ID"), "Name"),
]

# ── Job alert recipients (defaults to TELEGRAM_RECIPIENTS if not set) ────────
# Set to a subset if only you want job alerts, not colleagues.
JOB_RECIPIENTS = [
    (os.getenv("TELEGRAM_CHAT_ID"), "Aaron"),
]

# ══════════════════════════════════════════════════════════════════════════════
#  NEWS DIGEST SETTINGS
# ══════════════════════════════════════════════════════════════════════════════

# ── Schedule (SGT, UTC+8) ────────────────────────────────────────────────────
DAILY_TIMES = [
    (8, 0),     # 8:00 AM SGT
    (12, 0),    # 12:00 PM SGT
    (15, 0),    # 3:00 PM SGT
    (21, 25),   # 9:25 PM SGT
]

# ── Article filtering ─────────────────────────────────────────────────────────
ARTICLE_MAX_AGE_HOURS = 48
SKIP_UNDATED_ARTICLES = True
MAX_ARTICLES_PER_RUN  = 30

# ── Claude model ──────────────────────────────────────────────────────────────
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# ── RSS Feeds — verified, working sources (Apr 2025) ─────────────────────────
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

# ── Keywords — terms that indicate LNG relevance ─────────────────────────────
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

# ── Categories — for AI-driven grouping ──────────────────────────────────────
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
#  JOB SCRAPER SETTINGS
# ══════════════════════════════════════════════════════════════════════════════

# ── Job check schedule (SGT) ─────────────────────────────────────────────────
# Runs twice daily — morning and evening
JOB_TIMES = [
    (7, 30),    # 7:30 AM SGT — catch overnight postings
    (18, 0),    # 6:00 PM SGT — catch daytime postings
]

# ── Job feeds ─────────────────────────────────────────────────────────────────
# LinkedIn and Workday career portals don't offer RSS.
# Google News returns news articles, not job postings — don't use it here.
# For company-specific coverage, create Google Alerts (deliver to RSS feed)
# and paste the URLs into the GOOGLE_ALERTS section below.
JOB_FEEDS = [
    # --- Indeed RSS (keyword + location combos) ---
    # Singapore
    "https://www.indeed.com/rss?q=LNG&l=Singapore",
    "https://www.indeed.com/rss?q=liquefied+natural+gas&l=Singapore",
    "https://www.indeed.com/rss?q=LNG+trading&l=Singapore",
    "https://www.indeed.com/rss?q=gas+trading&l=Singapore",
    "https://www.indeed.com/rss?q=energy+trading&l=Singapore",
    # Houston
    "https://www.indeed.com/rss?q=LNG&l=Houston%2C+TX",
    "https://www.indeed.com/rss?q=LNG+trading&l=Houston%2C+TX",
    # London
    "https://www.indeed.com/rss?q=LNG+trading&l=London",
    "https://www.indeed.com/rss?q=LNG&l=London",
    # Tokyo
    "https://www.indeed.com/rss?q=LNG&l=Tokyo",

    # --- Specialist job boards ---
    "https://www.energyjobline.com/rss/all",
    "https://www.rigzone.com/jobs/rss/rigzone_jobs.aspx",

    # --- Google Alerts RSS (general web search, not news) ---
    # To add: go to google.com/alerts → create alert → set "Deliver to: RSS"
    # → copy the feed URL and paste here. Covers career pages Google indexes.
    # Example: "Shell LNG careers" alert would catch shell.wd3.myworkdayjobs.com
    # postings when Google indexes them.
    #
    # "https://www.google.com/alerts/feeds/YOUR_ALERT_ID_1/YOUR_FEED_ID_1",
    # "https://www.google.com/alerts/feeds/YOUR_ALERT_ID_2/YOUR_FEED_ID_2",
]

# ── Job keywords — at least one must match title or description ───────────────
# NOTE: These must be job-posting-specific terms, not general industry terms.
# "LNG" alone would match news articles. Use "LNG" + job-signal terms.
JOB_KEYWORDS = [
    # Job-specific LNG terms
    "lng job", "lng career", "lng hiring", "lng vacancy", "lng role",
    "lng analyst", "lng trader", "lng commercial", "lng manager",
    "lng engineer", "lng operator", "lng specialist",
    # Commercial & trading roles
    "gas trading", "energy trading", "commodity trading",
    "origination", "structuring", "portfolio manager",
    "commercial analyst", "commercial manager",
    # Quantitative & analytics roles
    "quant analyst", "quantitative analyst", "pricing analyst", "risk analyst",
    "valuation analyst", "modelling analyst", "optimization",
    # Role-type terms (these are specific enough to avoid news matches)
    "energy analyst", "gas analyst", "commodity analyst",
    "gas portfolio", "energy portfolio",
    # Broad job terms (combined with feed-level filtering these are safe)
    "natural gas analyst", "natural gas trader", "natural gas manager",
]

# ── Target companies — highlighted in alerts when matched ─────────────────────
JOB_TARGET_COMPANIES = [
    "jera", "shell", "bp", "totalenergies", "trafigura", "vitol",
    "gunvor", "pavilion energy", "sembcorp", "woodside", "cheniere",
    "venture global", "santos", "petronas", "equinor",
    "sempra", "conocophillips", "chevron",
]

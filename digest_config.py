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
# LinkedIn doesn't offer RSS; use saved search email alerts separately.
# Workday career portals (Shell, BP, etc.) don't offer RSS either —
# Google News search feeds below act as a catch-all for those.
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

    # --- Google News catch-all for IOC/major career postings ---
    # These pick up career page listings indexed by Google, covering
    # companies that don't syndicate to Indeed (Workday portals etc.)
    "https://news.google.com/rss/search?q=Shell+LNG+jobs+OR+careers+OR+hiring&hl=en&gl=SG&ceid=SG:en",
    "https://news.google.com/rss/search?q=BP+LNG+jobs+OR+careers+OR+hiring&hl=en&gl=SG&ceid=SG:en",
    "https://news.google.com/rss/search?q=TotalEnergies+LNG+jobs+OR+careers+OR+hiring&hl=en&gl=SG&ceid=SG:en",
    "https://news.google.com/rss/search?q=Chevron+LNG+jobs+OR+careers+OR+hiring&hl=en&gl=SG&ceid=SG:en",
    "https://news.google.com/rss/search?q=ExxonMobil+LNG+jobs+OR+careers+OR+hiring&hl=en&gl=SG&ceid=SG:en",
    "https://news.google.com/rss/search?q=Equinor+LNG+jobs+OR+careers+OR+hiring&hl=en&gl=SG&ceid=SG:en",
    "https://news.google.com/rss/search?q=ConocoPhillips+LNG+jobs+OR+careers+OR+hiring&hl=en&gl=SG&ceid=SG:en",
    "https://news.google.com/rss/search?q=Woodside+LNG+jobs+OR+careers+OR+hiring&hl=en&gl=SG&ceid=SG:en",
    "https://news.google.com/rss/search?q=JERA+LNG+jobs+OR+careers+OR+hiring&hl=en&gl=SG&ceid=SG:en",
    "https://news.google.com/rss/search?q=Trafigura+LNG+jobs+OR+careers+OR+hiring&hl=en&gl=SG&ceid=SG:en",
    "https://news.google.com/rss/search?q=Vitol+LNG+OR+gas+jobs+OR+careers+OR+hiring&hl=en&gl=SG&ceid=SG:en",
    "https://news.google.com/rss/search?q=Gunvor+LNG+OR+gas+jobs+OR+careers+OR+hiring&hl=en&gl=SG&ceid=SG:en",
    "https://news.google.com/rss/search?q=Cheniere+LNG+jobs+OR+careers+OR+hiring&hl=en&gl=SG&ceid=SG:en",
    "https://news.google.com/rss/search?q=Venture+Global+LNG+jobs+OR+careers+OR+hiring&hl=en&gl=SG&ceid=SG:en",
    "https://news.google.com/rss/search?q=Santos+LNG+jobs+OR+careers+OR+hiring&hl=en&gl=SG&ceid=SG:en",
    "https://news.google.com/rss/search?q=Petronas+LNG+jobs+OR+careers+OR+hiring&hl=en&gl=SG&ceid=SG:en",
    "https://news.google.com/rss/search?q=Sempra+LNG+jobs+OR+careers+OR+hiring&hl=en&gl=SG&ceid=SG:en",
    "https://news.google.com/rss/search?q=Pavilion+Energy+jobs+OR+careers+OR+hiring&hl=en&gl=SG&ceid=SG:en",
    "https://news.google.com/rss/search?q=Sembcorp+LNG+OR+gas+jobs+OR+careers+OR+hiring&hl=en&gl=SG&ceid=SG:en",

    # --- Broader LNG job searches via Google News ---
    "https://news.google.com/rss/search?q=LNG+trading+jobs+OR+careers+OR+hiring&hl=en&gl=SG&ceid=SG:en",
    "https://news.google.com/rss/search?q=LNG+origination+OR+structuring+jobs+OR+careers&hl=en&gl=SG&ceid=SG:en",
    "https://news.google.com/rss/search?q=gas+trading+analyst+OR+portfolio+jobs+OR+careers&hl=en&gl=SG&ceid=SG:en",
]

# ── Job keywords — at least one must match title or description ───────────────
JOB_KEYWORDS = [
    # Core LNG roles
    "lng", "liquefied natural gas",
    # Commercial & trading
    "gas trading", "energy trading", "commodity trading",
    "origination", "structuring", "portfolio",
    "commercial analyst", "commercial manager",
    # Quantitative & analytics
    "quant", "quantitative", "pricing analyst", "risk analyst",
    "valuation", "modelling", "optimization",
    # Specific companies (your target list)
    "jera", "shell", "bp", "totalenergies", "trafigura", "vitol",
    "gunvor", "pavilion energy", "sembcorp", "woodside", "cheniere",
    "venture global", "santos",
    # Specialist recruiters often tag roles with these
    "energy analyst", "gas analyst", "commodity analyst",
]

# ── Target companies — highlighted in alerts when matched ─────────────────────
JOB_TARGET_COMPANIES = [
    "jera", "shell", "bp", "totalenergies", "trafigura", "vitol",
    "gunvor", "pavilion energy", "sembcorp", "woodside", "cheniere",
    "venture global", "santos", "petronas", "equinor",
    "sempra", "conocophillips", "chevron",
]

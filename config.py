from dotenv import load_dotenv
import os

load_dotenv()

# ==========================================
# Recharge
# ==========================================

RECHARGE_TOKEN = os.getenv("RECHARGE_API_TOKEN")

if not RECHARGE_TOKEN:
    raise RuntimeError("RECHARGE_API_TOKEN is not configured.")

BASE_URL = os.getenv(
    "RECHARGE_BASE_URL",
    "https://api.rechargeapps.com"
)

RECHARGE_API_VERSION = os.getenv(
    "RECHARGE_API_VERSION",
    "2021-11",
)

HEADERS = {
    "X-Recharge-Access-Token": RECHARGE_TOKEN,
    "X-Recharge-Version": RECHARGE_API_VERSION,
    "Accept": "application/json",
    "Content-Type": "application/json",
}

# ==========================================
# Shopify
# ==========================================

SHOPIFY_STORE = os.getenv("SHOPIFY_STORE")

if not SHOPIFY_STORE:
    raise RuntimeError("SHOPIFY_STORE is not configured.")

SHOPIFY_CLIENT_ID = os.getenv("SHOPIFY_CLIENT_ID")

if not SHOPIFY_CLIENT_ID:
    raise RuntimeError("SHOPIFY_CLIENT_ID is not configured.")

SHOPIFY_API_SECRET = os.getenv("SHOPIFY_API_SECRET")

if not SHOPIFY_API_SECRET:
    raise RuntimeError("SHOPIFY_API_SECRET is not configured.")

SHOPIFY_ADMIN_API_VERSION = os.getenv(
    "SHOPIFY_ADMIN_API_VERSION",
    "2026-07",
)

SHOPIFY_WEBHOOK_SECRET = os.getenv(
    "SHOPIFY_WEBHOOK_SECRET",
    ""
)

# ==========================================
# Database
# ==========================================

DATABASE_URL = os.getenv("DATABASE_URL")
SYNC_API_KEY = os.getenv("SYNC_API_KEY", "")

# ==========================================
# CORS
# ==========================================

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "https://farmtohome.pt,"
    "http://localhost:9292,"
    "http://127.0.0.1:9292,"
    "https://extensions.shopifycdn.com"
).split(",")

# ==========================================
# Email Configuration
# ==========================================

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))

SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USERNAME)

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", SMTP_USERNAME)
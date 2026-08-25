from dotenv import load_dotenv
import os

load_dotenv()

RECHARGE_TOKEN = os.getenv("RECHARGE_API_TOKEN")
SHOPIFY_STORE = os.getenv("SHOPIFY_STORE")

SHOPIFY_API_SECRET = os.getenv("SHOPIFY_API_SECRET")

if not SHOPIFY_API_SECRET:
    raise RuntimeError("SHOPIFY_API_SECRET is not configured.")

BASE_URL = os.getenv(
    "RECHARGE_BASE_URL",
    "https://api.rechargeapps.com"
)

DATABASE_URL = os.getenv("DATABASE_URL")
SYNC_API_KEY = os.getenv("SYNC_API_KEY", "")

EXTRA_VARIANT_IDS = {
    int(value.strip())
    for value in os.getenv("EXTRA_VARIANT_IDS", "").split(",")
    if value.strip()
}

SHOPIFY_WEBHOOK_SECRET = os.getenv(
    "SHOPIFY_WEBHOOK_SECRET",
    ""
)

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "https://farmtohome.pt,"
    "http://localhost:9292,"
    "http://127.0.0.1:9292,"
    "https://extensions.shopifycdn.com"
).split(",")

if not RECHARGE_TOKEN:
    raise RuntimeError("RECHARGE_API_TOKEN is not configured.")

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
# Email Configuration (Google Workspace SMTP)
# ==========================================

# ==========================================
# Email Configuration (Google Workspace SMTP)
# ==========================================

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))

SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USERNAME)

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", SMTP_USERNAME)
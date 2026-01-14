# ================= config.py =================
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# -------- Telegram credentials (from .env) --------
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH")

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

# -------- Paths --------
JOBS_DIR = os.path.join(BASE_DIR, "jobs")
ALIASES_FILE = os.path.join(BASE_DIR, "aliases.json")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

# -------- Retry / worker config --------
MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))
RETRY_BACKOFF = list(
    map(int, os.getenv("RETRY_BACKOFF", "5,30,120").split(","))
)

# -------- Ensure folders exist --------
os.makedirs(JOBS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# create priority folders
for p in ("high", "normal", "low"):
    os.makedirs(os.path.join(JOBS_DIR, p), exist_ok=True)

# create aliases file if missing
if not os.path.exists(ALIASES_FILE):
    with open(ALIASES_FILE, "w") as f:
        f.write("{}")
# ==============================================

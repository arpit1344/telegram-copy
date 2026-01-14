import os

API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH")

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))

# convert "5,30,120" → [5,30,120]
RETRY_BACKOFF = list(
    map(int, os.getenv("RETRY_BACKOFF", "5,30,120").split(","))
)

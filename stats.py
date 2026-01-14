import json, os, time

STATS_FILE = "stats.json"

DEFAULT = {
    "start_time": time.time(),
    "messages_copied": 0,
    "errors": 0,
    "jobs_completed": 0
}

def load_stats():
    if os.path.exists(STATS_FILE):
        return json.load(open(STATS_FILE))
    return DEFAULT.copy()

def save_stats(s):
    json.dump(s, open(STATS_FILE, "w"), indent=2)

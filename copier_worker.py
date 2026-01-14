import time, json, os
from queue import fetch_job
from job_lock import unlock
from state import load_state
from stats import load_stats, save_stats

while True:
    STATE = load_state()

    if STATE.get("paused"):
        time.sleep(1)
        continue

    job, path = fetch_job()
    if not job:
        time.sleep(1)
        continue

    try:
        # 🔁 COPY ONE MESSAGE HERE
        job["cursor"] += 1
        job["retry"] = 0

        stats = load_stats()
        stats["messages_copied"] += 1
        save_stats(stats)

    except Exception:
        job["failures"] += 1
        stats = load_stats()
        stats["errors"] += 1
        save_stats(stats)

        if job["failures"] >= 10:
            job["status"] = "failed"

    finally:
        if os.path.exists(path):
            if job["status"] != "failed":
                unlock(job, path)
            else:
                json.dump(job, open(path, "w"), indent=2)

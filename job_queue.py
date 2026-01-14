# job_queue.py
# SAFE job fetcher (skips .gitkeep, corrupt json, empty files)

import os
import json
import time
import uuid

BASE = "jobs"
PRIORITY = ["high", "normal", "low"]

def fetch_job():
    for p in PRIORITY:
        folder = os.path.join(BASE, p)
        if not os.path.exists(folder):
            continue

        for f in os.listdir(folder):
            # ✅ only JSON files
            if not f.endswith(".json"):
                continue

            path = os.path.join(folder, f)

            try:
                with open(path, "r") as fp:
                    job = json.load(fp)
            except json.JSONDecodeError:
                # ❌ broken / empty file → delete
                os.remove(path)
                continue
            except Exception:
                continue

            # basic validation
            if job.get("status") in ("done", "failed"):
                continue

            return job, path

    return None, None

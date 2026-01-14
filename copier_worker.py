# copier_worker.py
# SAFE worker – never crashes on bad jobs

import time
import json
import os

from job_queue import fetch_job

print("🚀 Worker started")

while True:
    job, path = fetch_job()

    if not job:
        time.sleep(2)
        continue

    try:
        print(f"📦 Picked job: {path}")

        # ---- SIMULATED WORK ----
        # yahan tum telegram copy logic daal sakte ho
        time.sleep(1)

        job["status"] = "done"

        with open(path, "w") as fp:
            json.dump(job, fp, indent=2)

        print(f"✅ Job done: {path}")

    except Exception as e:
        print("❌ Job error:", e)
        job["status"] = "failed"
        with open(path, "w") as fp:
            json.dump(job, fp, indent=2)

    time.sleep(1)

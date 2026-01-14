# job_queue.py
import os, json

BASE = "jobs"
PRIORITY = ["high", "normal", "low"]

def fetch_job():
    for p in PRIORITY:
        folder = os.path.join(BASE, p)
        if not os.path.isdir(folder):
            continue

        for f in os.listdir(folder):
            # only real job files
            if not f.endswith(".json"):
                continue

            path = os.path.join(folder, f)

            try:
                with open(path, "r") as fp:
                    job = json.load(fp)
            except Exception:
                # corrupt / empty job
                try:
                    os.remove(path)
                except:
                    pass
                continue

            # skip non-runnable jobs
            if job.get("status") in ("paused", "done", "failed"):
                continue

            return job, path

    return None, None

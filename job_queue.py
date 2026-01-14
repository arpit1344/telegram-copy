import os, json
from config import JOBS_DIR, MAX_RETRIES

PRIORITY = ["high", "normal", "low"]
LOCK_EXT = ".lock"

def fetch_job():
    for pr in PRIORITY:
        folder = os.path.join(JOBS_DIR, pr)
        if not os.path.isdir(folder):
            continue

        for fn in os.listdir(folder):
            if not fn.endswith(".json"):
                continue

            path = os.path.join(folder, fn)
            lock = path + LOCK_EXT
            if os.path.exists(lock):
                continue

            try:
                job = json.load(open(path))
            except Exception:
                continue

            if job.get("status") not in ("running", "retrying"):
                continue

            open(lock, "w").write("locked")
            return job, path

    return None, None


def update_job(path, job):
    json.dump(job, open(path, "w"), indent=2)


def unlock_job(path):
    lock = path + LOCK_EXT
    if os.path.exists(lock):
        os.remove(lock)


def mark_failed(path, reason):
    job = json.load(open(path))
    retries = job.get("retry_count", 0)

    job["failed_reason"] = reason

    if retries < MAX_RETRIES:
        job["retry_count"] = retries + 1
        job["status"] = "retrying"
    else:
        job["status"] = "failed"

    update_job(path, job)
    unlock_job(path)

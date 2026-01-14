import os, json, time

BASE = "jobs"
PRIORITY = ["high", "normal", "low"]
LOCK_EXT = ".lock"

def fetch_job():
    """
    Fetch one runnable job and lock it.
    Returns (job_dict, job_path) or (None, None)
    """
    for pr in PRIORITY:
        folder = os.path.join(BASE, pr)
        if not os.path.isdir(folder):
            continue

        for fn in os.listdir(folder):
            if not fn.endswith(".json"):
                continue

            path = os.path.join(folder, fn)
            lock = path + LOCK_EXT

            # already locked by another worker
            if os.path.exists(lock):
                continue

            try:
                job = json.load(open(path))
            except Exception:
                continue

            if job.get("status") != "running":
                continue

            # 🔒 lock job
            open(lock, "w").write(str(os.getpid()))

            return job, path

    return None, None


def unlock_job(path):
    lock = path + LOCK_EXT
    if os.path.exists(lock):
        os.remove(lock)


def mark_failed(path, reason="unknown"):
    job = json.load(open(path))
    job["status"] = "failed"
    job["failed_reason"] = reason
    json.dump(job, open(path, "w"), indent=2)
    unlock_job(path)


def update_job(path, job):
    json.dump(job, open(path, "w"), indent=2)

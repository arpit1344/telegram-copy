import time, json, os, uuid

WORKER_ID = os.environ.get("WORKER_ID", str(uuid.uuid4())[:8])
LOCK_TIMEOUT = 30

def try_lock(job, path):
    now = time.time()
    if job.get("locked_by"):
        if now - job.get("lock_time", 0) < LOCK_TIMEOUT:
            return False

    job["locked_by"] = WORKER_ID
    job["lock_time"] = now
    job["status"] = "running"
    json.dump(job, open(path, "w"), indent=2)
    return True

def unlock(job, path):
    job["locked_by"] = None
    job["lock_time"] = None
    job["status"] = "pending"
    json.dump(job, open(path, "w"), indent=2)

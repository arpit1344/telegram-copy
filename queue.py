import os, json
from job_lock import try_lock

BASE = "jobs"
PRIORITY = ["high", "normal", "low"]

def all_jobs():
    jobs = []
    for p in PRIORITY:
        folder = os.path.join(BASE, p)
        for f in os.listdir(folder):
            path = os.path.join(folder, f)
            jobs.append((p, path))
    return jobs

def fetch_job():
    for p, path in all_jobs():
        job = json.load(open(path))
        if job["status"] in ("pending", "running"):
            if try_lock(job, path):
                return job, path
    return None, None

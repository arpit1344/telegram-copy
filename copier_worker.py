# copier_worker.py
import time, json
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from job_queue import fetch_job

# ===== TELEGRAM CONFIG =====
API_ID = 123456        # <-- YOUR API ID
API_HASH = "API_HASH"  # <-- YOUR API HASH
SESSION = "worker_session"
# ==========================

client = TelegramClient(SESSION, API_ID, API_HASH)
client.start()

print("🚀 Worker started")

while True:
    job, path = fetch_job()

    if not job:
        time.sleep(2)
        continue

    try:
        source = job["source"]
        target = job["target"]
        batch  = job.get("batch_size", 10)

        processed = job.get("processed_items", 0)
        total     = job.get("total_items", 0)
        last_id   = job.get("last_message_id", 0)

        # init start time once
        if "start_time" not in job:
            job["start_time"] = int(time.time())

        # init total messages once
        if total == 0:
            total = client.get_messages(source, limit=0).total
            job["total_items"] = total

        # iterate messages
        msgs = client.iter_messages(
            source,
            min_id=last_id,
            limit=batch
        )

        for msg in msgs:
            # pause support
            if job.get("status") == "paused":
                break

            try:
                client.send_message(target, msg)
            except FloodWaitError as e:
                time.sleep(e.seconds)
                continue

            last_id = msg.id
            processed += 1

            # speed + ETA
            now = time.time()
            elapsed = max(1, now - job["start_time"])
            speed = round(processed / elapsed, 2)
            remaining = max(0, total - processed)
            eta = int(remaining / speed) if speed > 0 else 0

            job.update({
                "processed_items": processed,
                "last_message_id": last_id,
                "progress": int((processed / total) * 100),
                "speed": speed,
                "eta_seconds": eta,
                "last_update": int(now),
                "status": "running"
            })

            json.dump(job, open(path, "w"), indent=2)
            time.sleep(0.5)

        # job finished
        if processed >= total:
            job["status"] = "done"
            json.dump(job, open(path, "w"), indent=2)

    except Exception as e:
        job["retry_count"] = job.get("retry_count", 0) + 1
        if job["retry_count"] > job.get("max_retries", 3):
            job["status"] = "failed"
        json.dump(job, open(path, "w"), indent=2)

    time.sleep(1)

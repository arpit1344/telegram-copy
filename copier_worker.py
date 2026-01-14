import os, time, asyncio, sys
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from job_queue import fetch_job, update_job, unlock_job, mark_failed

# ===== TELETHON CONFIG =====
API_ID = 123456        # <-- apna api_id
API_HASH = "API_HASH"  # <-- apna api_hash

WORKER_ID = os.environ.get("WORKER_ID", "1")
SESSION = f"user_session_{WORKER_ID}"

# ==========================

async def process_job(client, job, path):
    source = job["source"]
    target = job["target"]
    batch = job["batch_size"]

    start_time = time.time()
    processed = job.get("processed_items", 0)
    last_id = job.get("last_message_id", 0)

    try:
        async for msg in client.iter_messages(source, min_id=last_id, limit=batch):
            if msg.text:
                await client.send_message(target, msg.text)

            elif msg.media:
                await client.send_file(target, msg.media, caption=msg.text)

            processed += 1
            job["processed_items"] = processed
            job["last_message_id"] = msg.id

            elapsed = time.time() - start_time
            speed = processed / elapsed if elapsed > 0 else 0

            job["speed"] = round(speed, 2)
            job["progress"] = job.get("progress", 0)  # admin panel updates later
            job["eta_seconds"] = int((job.get("total_items", processed) - processed) / speed) if speed else 0

            update_job(path, job)

        # ✅ completed batch
        unlock_job(path)

    except FloodWaitError as e:
        await asyncio.sleep(e.seconds)
        unlock_job(path)

    except Exception as e:
        mark_failed(path, str(e))


async def worker_loop():
    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.start()

    print(f"🚀 Worker {WORKER_ID} started")

    while True:
        job, path = fetch_job()
        if not job:
            await asyncio.sleep(2)
            continue

        if job.get("status") != "running":
            unlock_job(path)
            continue

        await process_job(client, job, path)


if __name__ == "__main__":
    asyncio.run(worker_loop())

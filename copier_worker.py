import os, time, asyncio
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from job_queue import fetch_job, update_job, unlock_job, mark_failed
from config import API_ID, API_HASH, RETRY_BACKOFF
from dotenv import load_dotenv
load_dotenv(dotenv_path=".env")  # 👈 force load
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
API_ID = int(API_ID) if API_ID else None

WORKER_ID = os.getenv("WORKER_ID", "1")
SESSION = f"user_session_{WORKER_ID}"

async def process_job(client, job, path):
    source = job["source"]
    target = job["target"]
    batch = job["batch_size"]

    start = time.time()
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

            elapsed = time.time() - start
            speed = processed / elapsed if elapsed else 0

            job["speed"] = round(speed, 2)
            job["progress"] = min(100, int((processed / batch) * 100))
            job["eta_seconds"] = int((batch - processed) / speed) if speed else 0

            update_job(path, job)

        job["status"] = "completed"
        update_job(path, job)
        unlock_job(path)

    except FloodWaitError as e:
        await asyncio.sleep(e.seconds)
        mark_failed(path, f"FloodWait {e.seconds}s")

    except Exception as e:
        mark_failed(path, str(e))


async def worker_loop():
    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.start()

    while True:
        job, path = fetch_job()
        if not job:
            await asyncio.sleep(2)
            continue

        if job["status"] == "retrying":
            delay = RETRY_BACKOFF[min(job["retry_count"] - 1, len(RETRY_BACKOFF) - 1)]
            await asyncio.sleep(delay)
            job["status"] = "running"
            update_job(path, job)

        await process_job(client, job, path)

if __name__ == "__main__":
    asyncio.run(worker_loop())

print("DEBUG ENV FILE:", os.path.exists(".env"))
print("DEBUG API_ID:", API_ID)
print("DEBUG API_HASH:", API_HASH)


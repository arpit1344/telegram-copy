import os
import json
import asyncio
from datetime import datetime
from telethon import TelegramClient
from telethon.tl.types import MessageService
from dateutil.parser import parse

from job_queue import fetch_job, update_job, unlock_job, mark_failed

CFG = json.load(open("config.json"))
API_ID = CFG["api_id"]
API_HASH = CFG["api_hash"]

JOBS_DIR = "jobs"
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

def jp(jid):
    return f"{JOBS_DIR}/{jid}.json"

def load_job(jid):
    return json.load(open(jp(jid)))

def save_job(job):
    json.dump(job, open(jp(job["job_id"]), "w"), indent=2)

def log(jid, msg):
    with open(f"{LOGS_DIR}/{jid}.log", "a") as f:
        f.write(f"[{datetime.now()}] {msg}\n")

async def wait_if_paused(jid):
    while True:
        job = load_job(jid)
        if job.get("cancelled"):
            raise Exception("CANCELLED")
        if not job.get("paused"):
            return
        await asyncio.sleep(1)

async def run_job(job):
    jid = job["job_id"]

    # ✅ UNIQUE SESSION PER JOB (NO SQLITE LOCK)
    client = TelegramClient(f"job_{jid}", API_ID, API_HASH)
    await client.start()

    log(jid, "Worker started")

    try:
        for src in job["sources"]:
            src_entity = await client.get_entity(
                int(src) if str(src).startswith("-100") else src
            )

            async for msg in client.iter_messages(src_entity, reverse=True):
                job = load_job(jid)

                if job.get("cancelled"):
                    log(jid, "Job cancelled")
                    job["status"] = "cancelled"
                    save_job(job)
                    return

                await wait_if_paused(jid)

                if isinstance(msg, MessageService):
                    continue

                # 📅 DATE FILTER
                if job["date_mode"] != "all":
                    m = msg.date.date()
                    if job["date_mode"] == "single" and m != parse(job["from"]).date():
                        continue
                    if job["date_mode"] == "range":
                        if not (parse(job["from"]).date() <= m <= parse(job["to"]).date()):
                            continue

                for dest in job["destinations"]:
                    await wait_if_paused(jid)

                    dest_entity = await client.get_entity(
                        int(dest) if str(dest).startswith("-100") else dest
                    )

                    await client.send_message(dest_entity, msg)

                # 📈 PROGRESS UPDATE
                job = load_job(jid)
                job["progress"]["done"] += 1
                job["progress"]["last_message_id"] = msg.id
                save_job(job)

                interval = int(job.get("interval", 0))
                if interval > 0:
                    await asyncio.sleep(interval)

        job = load_job(jid)
        job["status"] = "completed"
        save_job(job)
        log(jid, "Job completed")

    except Exception as e:
        if str(e) == "CANCELLED":
            log(jid, "Stopped by cancel")
        else:
            log(jid, f"Worker error: {e}")
        raise

    finally:
        await client.disconnect()

async def main():
    while True:
        job, path = fetch_job()

        if not job:
            await asyncio.sleep(2)
            continue

        try:
            job["status"] = "running"
            update_job(path, job)

            await run_job(job)

            job["status"] = "completed"
            update_job(path, job)

        except Exception as e:
            mark_failed(path, str(e))

        finally:
            unlock_job(path)

if __name__ == "__main__":
    asyncio.run(main())

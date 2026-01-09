import os, json, asyncio
from datetime import datetime
from telethon import TelegramClient
from telethon.tl.types import MessageService
from dateutil.parser import parse

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

async def run_job(jid):
    client = TelegramClient("worker_session", API_ID, API_HASH)
    await client.start()

    log(jid, "Worker started")

    try:
        job = load_job(jid)
        job["status"] = "running"
        save_job(job)

        for src in job["sources"]:
            src_entity = await client.get_entity(
                int(src) if str(src).startswith("-100") else src
            )

            async for msg in client.iter_messages(src_entity):
                job = load_job(jid)

                # ❌ CANCEL IMMEDIATELY
                if job.get("cancelled"):
                    log(jid, "Job cancelled")
                    job["status"] = "cancelled"
                    save_job(job)
                    return

                # ⏸ STRICT PAUSE
                await wait_if_paused(jid)

                if isinstance(msg, MessageService):
                    continue

                # DATE FILTER
                if job["date_mode"] != "all":
                    m = msg.date.date()
                    if job["date_mode"] == "single" and m != parse(job["from"]).date():
                        continue
                    if job["date_mode"] == "range":
                        if not (parse(job["from"]).date() <= m <= parse(job["to"]).date()):
                            continue

                # SEND TO DESTINATIONS
                for dest in job["destinations"]:
                    await wait_if_paused(jid)

                    job = load_job(jid)
                    if job.get("cancelled"):
                        raise Exception("CANCELLED")

                    dest_entity = await client.get_entity(
                        int(dest) if str(dest).startswith("-100") else dest
                    )

                    await client.send_message(dest_entity, msg)

                # UPDATE PROGRESS
                job = load_job(jid)
                job["progress"]["done"] += 1
                save_job(job)

                # ⏱ INTERVAL AFTER EACH MESSAGE
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

    await client.disconnect()

async def main():
    while True:
        for f in os.listdir(JOBS_DIR):
            if not f.endswith(".json"):
                continue

            try:
                job = json.load(open(f"{JOBS_DIR}/{f}"))
            except:
                continue

            if job.get("status") == "running":
                await run_job(job["job_id"])

        await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())

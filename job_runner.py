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

def job_path(jid):
    return f"{JOBS_DIR}/{jid}.json"

def load_job(jid):
    return json.load(open(job_path(jid)))

def save_job(job):
    json.dump(job, open(job_path(job["job_id"]), "w"), indent=2)

def log(jid, msg):
    with open(f"{LOGS_DIR}/{jid}.log", "a") as f:
        f.write(f"[{datetime.now()}] {msg}\n")

async def run_job(jid):
    client = TelegramClient("worker_session", API_ID, API_HASH)
    await client.start()

    log(jid, "Worker started")

    while True:
        # 🔁 ALWAYS reload latest job state
        try:
            job = load_job(jid)
        except Exception:
            log(jid, "Job file missing, stopping worker")
            break

        # ❌ CANCEL IMMEDIATELY
        if job.get("cancelled"):
            log(jid, "Job cancelled by admin")
            break

        # ⏸ PAUSE LOOP
        if job.get("paused"):
            await asyncio.sleep(2)
            continue

        sources = job["sources"]
        destinations = job["destinations"]

        # loop through sources
        for src in sources:
            try:
                src_entity = await client.get_entity(
                    int(src) if str(src).startswith("-100") else src
                )
            except Exception as e:
                log(jid, f"Source access error {src}: {e}")
                continue

            async for msg in client.iter_messages(src_entity):
                # 🔁 RELOAD job INSIDE MESSAGE LOOP
                job = load_job(jid)

                if job.get("cancelled"):
                    log(jid, "Job cancelled during copy")
                    await client.disconnect()
                    return

                while job.get("paused"):
                    await asyncio.sleep(2)
                    job = load_job(jid)

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

                for dest in destinations:
                    try:
                        dest_entity = await client.get_entity(
                            int(dest) if str(dest).startswith("-100") else dest
                        )
                        await client.send_message(dest_entity, msg)
                    except Exception as e:
                        log(jid, f"Send failed: {e}")

                # ✅ UPDATE PROGRESS SAFELY
                job["progress"]["done"] += 1
                save_job(job)

        # all done
        job["status"] = "completed"
        save_job(job)
        log(jid, "Job completed")
        break

    await client.disconnect()

async def main():
    for f in os.listdir(JOBS_DIR):
        if not f.endswith(".json"):
            continue

        try:
            job = json.load(open(f"{JOBS_DIR}/{f}"))
        except Exception:
            continue

        if job.get("status") == "running":
            await run_job(job["job_id"])

if __name__ == "__main__":
    asyncio.run(main())

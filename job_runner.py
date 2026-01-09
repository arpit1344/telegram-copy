import os, json, asyncio
from telethon import TelegramClient
from telethon.tl.types import MessageService
from dateutil.parser import parse
from datetime import datetime

CFG = json.load(open("config.json"))
API_ID = CFG["api_id"]
API_HASH = CFG["api_hash"]

JOBS_DIR = "jobs"
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

def log(jid, msg):
    with open(f"{LOGS_DIR}/{jid}.log", "a") as f:
        f.write(f"[{datetime.now()}] {msg}\n")

async def run_job(job):
    client = TelegramClient("worker_session", API_ID, API_HASH)
    await client.start()

    log(job["job_id"], "Worker started")

    for src in job["sources"]:
        try:
            src_entity = await client.get_entity(
                int(src) if str(src).startswith("-100") else src
            )
        except Exception as e:
            log(job["job_id"], f"Cannot access source {src}: {e}")
            continue

        async for msg in client.iter_messages(src_entity):
            if job.get("cancelled"):
                log(job["job_id"], "Job cancelled")
                await client.disconnect()
                return

            while job.get("paused"):
                await asyncio.sleep(2)
                job = json.load(open(f"jobs/{job['job_id']}.json"))

            if isinstance(msg, MessageService):
                continue

            if job["date_mode"] != "all":
                m = msg.date.date()
                if job["date_mode"] == "single" and m != parse(job["from"]).date():
                    continue
                if job["date_mode"] == "range":
                    if not (parse(job["from"]).date() <= m <= parse(job["to"]).date()):
                        continue

            for dest in job["destinations"]:
                try:
                    dest_entity = await client.get_entity(
                        int(dest) if str(dest).startswith("-100") else dest
                    )
                    await client.send_message(dest_entity, msg)
                except Exception as e:
                    log(job["job_id"], f"Send failed: {e}")

            job["progress"]["done"] += 1
            json.dump(job, open(f"jobs/{job['job_id']}.json", "w"), indent=2)

    job["status"] = "completed"
    json.dump(job, open(f"jobs/{job['job_id']}.json", "w"), indent=2)
    log(job["job_id"], "Job completed")

    await client.disconnect()

async def main():
    for f in os.listdir(JOBS_DIR):
        if not f.endswith(".json"):
            continue

        path = f"{JOBS_DIR}/{f}"

        # 🔒 SAFETY: ignore empty/corrupt jobs
        try:
            job = json.load(open(path))
        except Exception:
            print(f"[SKIP] Invalid job file: {f}")
            continue

        if job.get("status") == "running":
            await run_job(job)

if __name__ == "__main__":
    asyncio.run(main())

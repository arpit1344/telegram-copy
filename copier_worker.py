import asyncio, json, os
from datetime import datetime
from dateutil.parser import parse
from telethon import TelegramClient
from telethon.tl.types import MessageService
from telethon.errors import FloodWaitError

def log(jid, msg):
    os.makedirs("logs", exist_ok=True)
    with open(f"logs/{jid}.log", "a") as f:
        f.write(f"[{datetime.now()}] {msg}\n")

async def run_job(job_file, api_id, api_hash):
    job = json.load(open(job_file))
    jid = job["job_id"]

    client = TelegramClient(f"session_{jid}", api_id, api_hash)
    await client.start()
    log(jid, "Job started")

    for src in job["sources"]:
        last_id = job["resume"].get(str(src), 0)

        async for msg in client.iter_messages(src, min_id=last_id):
            job = json.load(open(job_file))

            if job["cancelled"]:
                log(jid, "Cancelled")
                return

            while job["paused"]:
                await asyncio.sleep(2)
                job = json.load(open(job_file))

            if isinstance(msg, MessageService):
                continue

            if job["date_mode"] != "all":
                mdate = msg.date.date()
                if job["date_mode"] == "single":
                    if mdate != parse(job["from"]).date():
                        continue
                if job["date_mode"] == "range":
                    if not (parse(job["from"]).date() <= mdate <= parse(job["to"]).date()):
                        continue

            try:
                for dst in job["destinations"]:
                    if msg.media:
                        await client.send_file(dst, msg.media, caption=msg.text or "")
                    elif msg.text:
                        await client.send_message(dst, msg.text)

                job["resume"][str(src)] = msg.id
                job["progress"]["done"] += 1

                if job["progress"]["done"] % job["batch"] == 0:
                    await asyncio.sleep(2)

            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)

            json.dump(job, open(job_file, "w"), indent=2)

    job["status"] = "completed"
    log(jid, "Completed")
    json.dump(job, open(job_file, "w"), indent=2)

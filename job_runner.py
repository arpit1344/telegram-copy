import os, asyncio, json
from copier_worker import run_job

cfg = json.load(open("config.json"))

async def main():
    tasks = []
    for f in os.listdir("jobs"):
        job = json.load(open(f"jobs/{f}"))
        if job["status"] in ["created", "running"]:
            tasks.append(run_job(f"jobs/{f}", cfg["api_id"], cfg["api_hash"]))
    await asyncio.gather(*tasks)

asyncio.run(main())

import asyncio
import os
from dotenv import load_dotenv

load_dotenv(".env")

async def main():
    print("🚀 Copier Worker started", flush=True)

    # job_runner handles everything
    from job_runner import main as runner_main
    await runner_main()

if __name__ == "__main__":
    asyncio.run(main())

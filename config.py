import asyncio, os

DOWNLOAD_PATH = "D:\\Programs\\Python\\Files\\Downloads\\Videos"
DOWNLOAD_SEM = asyncio.Semaphore(2)
QUERY_SEM = asyncio.Semaphore(3)
INITIAL_PATH = "D:\\Programs\\Python\\Files\\Downloads\\Videos\\Initials"
os.makedirs(DOWNLOAD_PATH, exist_ok=True)
os.makedirs(INITIAL_PATH, exist_ok=True)

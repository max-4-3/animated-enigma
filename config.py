import asyncio, os

DOWNLOAD_PATH = r"D:\Programs\Python\Files\Downloads\Videos" if os.name in ['windows', 'nt'] else os.path.expanduser('~/Downloads/Videos')
DOWNLOAD_SEM = asyncio.Semaphore(2)
QUERY_SEM = asyncio.Semaphore(3)
INITIAL_PATH = os.path.join(DOWNLOAD_PATH, 'Initials')
os.makedirs(DOWNLOAD_PATH, exist_ok=True)
os.makedirs(INITIAL_PATH, exist_ok=True)

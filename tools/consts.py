import os

LOG_PATH = os.path.join(os.path.dirname((os.path.dirname(__file__))), "Logs")
os.makedirs(LOG_PATH, exist_ok=True)
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [PID:%(process)d] [%(threadName)s] [%(funcName)s@%(filename)s:%(lineno)d] - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


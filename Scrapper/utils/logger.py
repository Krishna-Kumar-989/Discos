from datetime import datetime
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = str(LOG_DIR / "scraper.log")

def log(message):

    timestamp = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    formatted = f"[{timestamp}] {message}"

    print(formatted)

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(formatted + "\n")
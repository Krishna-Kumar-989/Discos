import os
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=project_root / ".env")

TOKEN = os.getenv("DISCORD_TOKEN")

SKIP_EXISTING = True

DOWNLOAD_ATTACHMENTS = False

# Local dir for attachments (if enabled)
ATTACHMENTS_DIR = str(project_root / "scrapedData" / "attachments")
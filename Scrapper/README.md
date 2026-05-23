# Discord Scraper

The `Scrapper` module connects to the Discord API via bot credentials and crawls message histories from all accessible channels and threads in a target guild. Scraped data is streamed directly to the configured **Object Store** (MinIO/S3), so no local files are written.

## Object Key Convention

Exports are stored in the Object Store using this path pattern:

```
<bucket>/discord_exports/<guild_id>/<channel_name>_<date>.json
```

Each JSON file contains the following fields:
- `guild`, `guild_id` — Server name and ID.
- `channel`, `channel_id` — Channel name and ID.
- `date` — Date of the scraped messages.
- `message_count` — Number of messages in the file.
- `messages` — List of message objects, each including:
  - `id`, `author`, `timestamp`, `content`
  - `replies`, `reactions`, `embeds`, `attachments`

## Configuration

Key settings in `config.py`:
- `SKIP_EXISTING` — If `True`, skips uploading a file if an object with the same key already exists in the store (incremental scraping).
- `DOWNLOAD_ATTACHMENTS` — If `True`, also saves attachment files locally (to `ATTACHMENTS_DIR`).

## Installation

```bash
pip install -r requirements.txt
```

## Usage

Run the scraper interactively from the project root:

```bash
python Endpoint/scrapper_endpoint/cli.py
```

Or trigger it programmatically:
```python
from Endpoint import trigger_scrapper
await trigger_scrapper(server_id="1234567890")
```
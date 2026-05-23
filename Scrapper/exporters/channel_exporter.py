import json

from pathlib import Path

from exporters.message_serializer import serialize_message
from utils.file_utils import sanitize_filename
from utils.date_utils import get_date_string
from utils.logger import log
from config import SKIP_EXISTING

from objectStore import get_object_store
import io


async def export_channel(
    channel,
    guild_id,
    guild_name
):

    log(f"Exporting #{channel.name}")

    messages_by_date = {}

    async for msg in channel.history(
        limit=None,
        oldest_first=True
    ):

        date_str = get_date_string(
            msg.created_at
        )

        if date_str not in messages_by_date:
            messages_by_date[date_str] = []

        messages_by_date[date_str].append(
            serialize_message(msg)
        )

    store = get_object_store()
    # Create the root bucket if it doesn't exist
    store.create_bucket()

    for date_str, messages in messages_by_date.items():
        object_name = f"discord_exports/{str(guild_id)}/{sanitize_filename(channel.name)}_{date_str}.json"

        if SKIP_EXISTING and store.object_exists(object_name):
            log(f"Skipping {object_name}")
            continue

        payload = {
            "guild": guild_name,
            "guild_id": str(guild_id),
            "channel": channel.name,
            "channel_id": str(channel.id),
            "date": date_str,
            "message_count": len(messages),
            "messages": messages
        }

        json_bytes = json.dumps(payload, indent=2, ensure_ascii=False).encode('utf-8')
        data_stream = io.BytesIO(json_bytes)

        store.upload_object(object_name, data_stream, content_type="application/json")

        log(f"Saved {object_name} to object store")
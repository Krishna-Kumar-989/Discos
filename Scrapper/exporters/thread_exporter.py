from exporters.channel_exporter import (
    export_channel
)

from utils.logger import log


async def export_threads(guild):

    for thread in guild.threads:

        try:

            await export_channel(
                thread,
                str(guild.id),
                guild.name
            )

        except Exception as e:

            log(
                f"Thread error "
                f"{thread.name}: {e}"
            )
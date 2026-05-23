import logging
import asyncio
import discord
from discord.ext import commands

from Endpoint.scrapper_endpoint.trigger import trigger_scrapper
from Endpoint.ingestion_endpoint.trigger import trigger_ingestion

async def run_eat_pipeline(interaction: discord.Interaction):
    """
    Background pipeline to scrape and then ingest the server data sequentially.
    """
    server_id = str(interaction.guild.id)
    
    #Scrape
    scrape_result = await trigger_scrapper(server_id=server_id)
    if scrape_result.get("status") != "success":
        error_msg = scrape_result.get("error", "Unknown scraping error")
        await interaction.followup.send(f"❌ Scraping failed: {error_msg}", ephemeral=True)
        return

    await interaction.followup.send("✅ Scraping complete! Now ingesting data into the Vector Database...", ephemeral=True)

    #Ingest
    # `trigger_ingestion` is a synchronous blocking function, so we run it in an executor
    loop = asyncio.get_running_loop()
    try:
        ingest_result = await loop.run_in_executor(
            None, 
            trigger_ingestion, 
            server_id, 
            False # rebuild=False
        )
        
        if ingest_result.get("status") != "success":
            error_msg = ingest_result.get("error", "Unknown ingestion error")
            await interaction.followup.send(f"❌ Ingestion failed: {error_msg}", ephemeral=True)
            return
            
        await interaction.followup.send("🎉 **'Eat' Pipeline finished successfully!** Server knowledge base is now up to date.", ephemeral=True)
    except Exception as e:
        logging.error(f"Error during ingestion in eat pipeline: {e}", exc_info=True)
        await interaction.followup.send(f"❌ An error occurred during ingestion: {e}", ephemeral=True)


class ConfigSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Eat", 
                description="Scrape and ingest the current server data.", 
                emoji="🍽️",
                value="eat"
            )
        ]
        super().__init__(
            placeholder="Choose a configuration action...", 
            min_values=1, 
            max_values=1, 
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "eat":
            #Respond to the interaction immediately to prevent timeout
            await interaction.response.send_message("Initiating the 'Eat' process in the background. Scraping data first...", ephemeral=True)
            #Create a background task for the actual pipeline
            interaction.client.loop.create_task(run_eat_pipeline(interaction))


class ConfigView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(ConfigSelect())


class ConfigCog(commands.Cog):
    """
    Commands for configuring the server and managing data pipelines.
    """
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="config")
    async def config(self, ctx):
        """
        Open the interactive server configuration menu.
        Usage: !config
        """
        if not ctx.guild:
            await ctx.send("This command can only be used in a Discord server, not in Direct Messages.")
            return
            
        await ctx.send("⚙️ **Server Configuration**\nPlease select an action below:", view=ConfigView())


async def setup(bot):
    await bot.add_cog(ConfigCog(bot))

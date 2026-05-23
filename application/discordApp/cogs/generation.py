import logging
import discord
from discord.ext import commands

from Endpoint.generation_endpoint.query import query_generation_pipeline

class Generation(commands.Cog):
    """
    Commands related to answer generation and text summarization workflows.
    """
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="ask")
    async def ask(self, ctx, *, question: str):
        """
        Ask a question about the server's knowledge base.
        Usage: !ask <your question>
        """
      
        if not ctx.guild:
            await ctx.send("This command can only be used in a Discord server, not in Direct Messages.")
            return

        server_id = str(ctx.guild.id)
        
        # Send a typing indicator to Discord while the RAG pipeline is processing
        async with ctx.typing():
            try:
                result = await query_generation_pipeline(
                    query=question, 
                    server_id=server_id,
                    user_id=str(ctx.author.id)
                )
                answer = result.get("response", "I could not generate an answer.")
                
                #chunk if charchter limit exceeded
                if len(answer) > 2000:
                    chunks = [answer[i:i+1990] for i in range(0, len(answer), 1990)]
                    for chunk in chunks:
                        await ctx.send(chunk)
                else:
                    await ctx.send(answer)
                    
            except Exception as e:
                error_msg = f"An error occurred while generating the answer: {e}"
                await ctx.send(error_msg)
                logging.error(f"Error during query execution: {e}", exc_info=True)

    @commands.command(name="summary")
    async def summary(self, ctx, *, prompt: str):
        """
        Trigger the summarization pipeline for the server based on a prompt.
        Usage: !summary <your prompt>
        """
       
        if not ctx.guild:
            await ctx.send("This command can only be used in a Discord server, not in Direct Messages.")
            return

        server_id = str(ctx.guild.id)
        
        #Send a typing indicator to Discord while the RAG pipeline is processing
        async with ctx.typing():
            try:
                result = await query_generation_pipeline(
                    query=prompt, 
                    server_id=server_id, 
                    workflow_type="Summary_workflow",
                    user_id=str(ctx.author.id)
                )
                answer = result.get("response", "I could not generate a summary.")
                
                # Discord messages have a 2000 character limit. Chunk if necessary.
                if len(answer) > 2000:
                    chunks = [answer[i:i+1990] for i in range(0, len(answer), 1990)]
                    for chunk in chunks:
                        await ctx.send(chunk)
                else:
                    await ctx.send(answer)
                    
            except Exception as e:
                error_msg = f"An error occurred while generating the summary: {e}"
                await ctx.send(error_msg)
                logging.error(f"Error during summary execution: {e}", exc_info=True)

async def setup(bot):
    await bot.add_cog(Generation(bot))

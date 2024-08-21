from discord import Interaction
from discord.ext.commands import Context
from ..bot import bot

@bot.tree.command()
async def ping(interaction: Interaction):
    await interaction.response.send_message('Hellosu!')

@bot.command()
async def ping(ctx: Context):
    await ctx.send('Hellosu!')

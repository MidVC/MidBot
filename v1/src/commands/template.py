from discord import Interaction
from discord.ext.commands import Context
from ..bot import bot

@bot.tree.command()
async def cmd(interaction: Interaction):
    await interaction.response.send_message('cmd')

@bot.command()
async def cmd(ctx: Context):
    await ctx.send('cmd')
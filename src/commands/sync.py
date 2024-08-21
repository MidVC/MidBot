from discord import Interaction
from discord.ext import commands
from ..bot import bot

async def __syncCommands() -> int:
    synced = await bot.tree.sync()
    print('synced', len(synced), 'command(s)')
    return len(synced)

@bot.tree.command()
@commands.is_owner()
async def sync(interaction: Interaction):
    await interaction.response.defer(thinking=True)
    synced = await __syncCommands()
    await interaction.edit_original_response(content='synced '+str(synced)+' commands')

@bot.command()
@commands.is_owner()
async def sync(ctx: commands.Context):
    await ctx.send('synced ' + str(await __syncCommands()) + ' commands')

import random
from discord import Interaction
from discord.ext.commands import Context
from typing import Optional
from ..bot import bot

def handle_roll(range: int) -> str:
    if range <= 0:
        return 'Wdym roll ' + str(range) + ' ?!'
    return str(random.randint(1, range))


@bot.tree.command()
async def roll(interaction: Interaction, num: Optional[int] = 100):
    await interaction.response.send_message(handle_roll(num))

@bot.command()
async def roll(ctx: Context, num: int = 100):
    await ctx.send(handle_roll(num))

import os
from .classes.discordBot import DiscordBot

__token = os.environ.get('BOTTOKEN')
bot = DiscordBot(token=__token, description="MidBot!", prefix='!')

from .commands import *

def run_discord_bot():
    bot.run()

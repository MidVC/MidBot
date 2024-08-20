from .classes.discordBot import discordBot


def run_discord_bot(token: str):
    bot = discordBot(token=token, description="MidBot!", prefix='!')
    bot.run()
        

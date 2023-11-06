import os
from dotenv import load_dotenv
from src.bot import run_discord_bot

load_dotenv('.env.example')

if __name__ == '__main__':
    token = os.environ.get('TOKEN')
    osuApiKey = os.environ.get('OSUAPIKEY')
    run_discord_bot(token, osuApiKey)

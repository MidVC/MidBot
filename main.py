import os
from dotenv import load_dotenv
load_dotenv('.env.example')

from src.bot import run_discord_bot
from utils.DiscordToOsuID import closeConnection as closeDiscordToOsuIDConnection

if __name__ == '__main__':
    try:
        token = os.environ.get('BOTTOKEN')
        clientId = os.environ.get('OAUTHCLIENTID')
        clientSecret = os.environ.get('OAUTHCLIENTSECRET')
        osuApiKey = os.environ.get('OSUAPIKEY')
        run_discord_bot(token, osuApiKey, clientId, clientSecret)
    finally:
        closeDiscordToOsuIDConnection()
        print('exitted due to KeyboardInterrupt')

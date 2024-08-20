import os
from dotenv import load_dotenv
load_dotenv('.env.midc')

from src.bot_old import run_discord_bot

if __name__ == '__main__':
    try:
        token = os.environ.get('BOTTOKEN')
        clientId = os.environ.get('OAUTHCLIENTID')
        clientSecret = os.environ.get('OAUTHCLIENTSECRET')
        osuApiKey = os.environ.get('OSUAPIKEY')
        run_discord_bot(token, osuApiKey, clientId, clientSecret)
    finally:
        print('exitted the program')

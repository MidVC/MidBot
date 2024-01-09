import os
from dotenv import load_dotenv
from src.bot import run_discord_bot

load_dotenv('.env.example')

if __name__ == '__main__':
    token = os.environ.get('BOTTOKEN')
    clientId = os.environ.get('OAUTHCLIENTID')
    clientSecret = os.environ.get('OAUTHCLIENTSECRET')
    osuApiKey = os.environ.get('OSUAPIKEY')
    run_discord_bot(token, osuApiKey, clientId, clientSecret)

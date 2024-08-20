import os
from dotenv import load_dotenv
load_dotenv('.env.example')

from src.bot import run_discord_bot

if __name__ == '__main__':
    try:
        token = os.environ.get('BOTTOKEN')
        run_discord_bot(token=token)
    finally:
        print('exitted the program')

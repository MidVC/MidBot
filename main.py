from dotenv import load_dotenv
load_dotenv('.env.example')

from src.bot import run_discord_bot

if __name__ == '__main__':
    try:
        run_discord_bot()
    finally:
        print('exitted the program')

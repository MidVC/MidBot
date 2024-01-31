import discord
from .responses import handle_response


async def send_message(message, clientId, clientSecret, isPrivate=False):
    try:
        response = handle_response(message, clientId, clientSecret)
        if response == '':
            return
        if isPrivate:
            await message.author.send(response)
        else:
            await message.channel.send(response)

    except Exception as e:
        print(e)


intent = discord.Intents.default()
intent.message_content = True
client = discord.Client(intents=intent)

def run_discord_bot(token, apiKey, clientId, clientSecret):

    @client.event
    async def on_ready():
        print(f'{client.user} is now running!')

    @client.event
    async def on_message(message):
        if message.author == client.user:
            return

        username = message.author
        user_message = message.content
        channel = message.channel

        print(f'{username} said {user_message} in {channel}')

        await send_message(message, clientId, clientSecret)
    
    client.run(token)

async def stopDiscordBot():
    await client.close()

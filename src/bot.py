import discord
from .responses import handle_response


async def send_message(message, user_message, is_private):
    try:
        response = handle_response(user_message)
        if is_private:
            await message.author.send(response)
        else:
            await message.channel.send(response)

    except Exception as e:
        print(e)


def run_discord_bot():
    TOKEN = 'MTE3MDk5OTE1NDk2OTk0ODIxMA.GI2O9j.6YitaKpKMnj5fDQzjmTQ0KGfTArcSNr_8C_Zo8'
    intent = discord.Intents.default()
    intent.message_content = True
    client = discord.Client(intents=intent)

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

        await send_message(message, user_message, is_private=False)

    client.run(TOKEN)

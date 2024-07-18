from discord import Client

async def sendMessageUser(client: Client, userID: int, message: str):
    user = await client.fetch_user(userID)
    if user:
        await user.send(message)

async def sendMessageChannel(client: Client, channelID: int, message: str):
    channel = await client.fetch_channel(channelID)
    if channel:
        await channel.send(message)
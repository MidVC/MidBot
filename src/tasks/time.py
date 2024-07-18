from .utils import sendMessageChannel, sendMessageUser
from discord import Client
from datetime import datetime, time
from sys import stderr
from discord.ext import tasks


sendTimeUsers = [(848463695998353459, False)]
sendTimeChannels = [(1194446562919710764, True)]

@tasks.loop(time=time(2, 4))
async def taskTime(client: Client):
    try:
        for user in sendTimeUsers:
            if user[1]:
                await sendMessageUser(client, user[0], 'Time')
        for channel in sendTimeChannels:
            if channel[1]:
                await sendMessageChannel(client, channel[0], 'Time')
    except Exception as e:
        print(e, file=stderr)
    
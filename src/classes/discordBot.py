from sys import stderr

from discord.ext.commands import Bot
from discord import Message, Intents

from ..tasklist import startAllTasks
from ..responses import handle_response

class discordBot(Bot):
    def __init__(self, token: str, description: str = "", prefix: str = '!'):
        self.__token = token
        self.description = description
        self.prefix = prefix
        intent = Intents.default()
        intent.message_content = True
        super().__init__(command_prefix=prefix, intents=intent)

    def run(self):
        super().run(token=self.__token)

    async def on_ready(self):
        startAllTasks(self)
        print("Logged in as ", self.user)

    async def on_message(self, message:Message):
        if message.author == self.user:
            return

        username = message.author
        user_message = message.content
        channel = message.channel
        print(f'{username} said {user_message} in {channel}')

        await self._send_message(message)
    
    async def _send_message(self, message:Message):
        try:
            response = handle_response(self, message)
            if response == '':
                return
            await message.channel.send(response)
            print("Sent", response, "to", message.channel)

        except Exception as e:
            print(e, file=stderr)

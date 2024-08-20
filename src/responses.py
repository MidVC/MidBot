from .handlers.roll import handle_roll
from .handlers.rs import handle_rs
from .handlers.derankerrs import handle_deranker_rs
from .handlers.ciallo import handleCiallo
from discord import Client, Message
from discord.ext.commands import Bot

# def handle_response(client: Client, message, clientId, clientSecret) -> str:
#     lc_message = message.content.lower()

#     words = lc_message.split(' ')
    
#     if words[0] == '!roll':
#         if len(words) == 1 or not words[1].isnumeric():
#             return handle_roll(100)
#         else:
#             return handle_roll(int(words[1]))
#     elif words[0] == '>rs':
#         if len(words) > 1:
#             return handle_rs(words[1], clientId, clientSecret) + "\n" + handle_deranker_rs(message.author.id)
#     elif "ciallo" in lc_message:
#         return handleCiallo()

#     return ''

def handle_response(bot: Bot, message:Message) -> str:
    lc_message = message.content.lower()

    words = lc_message.split(' ')
    
    if words[0] == '!roll':
        if len(words) == 1 or not words[1].isnumeric():
            return handle_roll(100)
        else:
            return handle_roll(int(words[1]))
    elif words[0] == '>rs':
        if len(words) > 1:
            return handle_rs(words[1]) + "\n" + handle_deranker_rs(message.author.id)
    elif "ciallo" in lc_message:
        return handleCiallo()

    return ''

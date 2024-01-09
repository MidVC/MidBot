from .handlers.roll import handle_roll
from .handlers.derankerrs import handle_deranker_rs

def handle_response(message) -> str:
    lc_message = message.content.lower()

    words = lc_message.split(' ')
    
    if words[0] == '!roll':
        if len(words) == 1 or not words[1].isnumeric():
            return handle_roll(100)
        else:
            return handle_roll(int(words[1]))
    elif words[0] == '>rs':
        print(message.author)
        return handle_deranker_rs(str(message.author))

    return ''

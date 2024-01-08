from .handlers.roll import handle_roll

def handle_response(message) -> str:
    lc_message = message.lower()

    if lc_message == '>rs':
        return 'deranker!'

    words = message.split(' ')
    
    if words[0] == '!roll':
        if len(words) == 1 or not words[1].isnumeric():
            return handle_roll(100)
        else:
            return handle_roll(int(words[1]))

    return ''

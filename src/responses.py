def handle_response(message) -> str:
    lc_message = message.lower()

    if lc_message == '>rs':
        return 'deranker!'

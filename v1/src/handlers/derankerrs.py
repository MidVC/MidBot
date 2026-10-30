derankerIdList = []

def handle_deranker_rs(id: int) -> str :
    if id in derankerIdList :
        return "deranker!"
    return ''

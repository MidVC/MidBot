derankerIdList = ["whitegengar1"]

def handle_deranker_rs(id: str) -> str :
    if id in derankerIdList :
        return "deranker!"
    return ''

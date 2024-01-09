derankerIdList = [389238231465459712, 848463695998353459]

def handle_deranker_rs(id: int) -> str :
    if id in derankerIdList :
        return "deranker!"
    return ''

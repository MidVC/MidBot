from ossapi import Ossapi

def handle_rs(user_name: str, clientId, clientSecret) -> str :
    api = Ossapi(clientId, clientSecret)
    user_id = api.user(user=user_name).id
    scoreList = api.user_scores(user_id, "recent", include_fails=True, mode="osu", limit=10, offset=0)
    if len(scoreList) == 0:
        return "User " + user_name + " does not have a recent play on bancho!"
    return ("None pp on " if scoreList[0].pp == None else "{:.2f}".format(scoreList[0].pp) + "pp on ") + \
            scoreList[0].beatmapset.title + " +" + \
            str(scoreList[0].mods) + ", " + \
            "{:.2f}".format(scoreList[0].accuracy * 100) + "%, " + \
            str(scoreList[0].max_com) + "x"
           

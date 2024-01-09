from ossapi import Ossapi

def handle_rs(user_name: str, clientId, clientSecret) -> str :
    api = Ossapi(clientId, clientSecret)
    user_id = api.user(user=user_name).id
    scoreList = api.user_scores(user_id, "recent", include_fails=True, mode="osu", limit=10, offset=0)
    return str(scoreList[0].pp) + "pp on " + \
            scoreList[0].beatmapset.title + " +" + \
            str(scoreList[0].mods) + ", " + str(scoreList[0].accuracy) + "%, " + \
            str(scoreList[0].max_combo) + "x"
           

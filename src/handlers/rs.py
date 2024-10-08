import os
from ossapi import Ossapi

# def handle_rs(user_name: str, clientId, clientSecret) -> str :
#     api = Ossapi(clientId, clientSecret)

#     # check user not found
#     try:
#         user_id = api.user(user=user_name).id
#     except:
#         return "User " + user_name + " not found!"
    
#     scoreList = api.user_scores(user_id, "recent", include_fails=True, mode="osu", limit=10, offset=0)

#     # check no recent score
#     if len(scoreList) == 0:
#         return "User " + user_name + " does not have a recent play on bancho!"
    
#     return ("None pp on " if scoreList[0].pp == None else "{:.2f}".format(scoreList[0].pp) + "pp on ") + \
#             scoreList[0].beatmapset.title + " +" + \
#             str(scoreList[0].mods) + ", " + \
#             "{:.2f}".format(scoreList[0].accuracy * 100) + "%, " + \
#             str(scoreList[0].max_combo) + "x"

def handle_rs(user_name: str) -> str :

    clientId = os.environ.get('OAUTHCLIENTID')
    clientSecret = os.environ.get('OAUTHCLIENTSECRET')
    
    api = Ossapi(clientId, clientSecret)

    # check user not found
    try:
        user_id = api.user(user=user_name).id
    except:
        return "User " + user_name + " not found!"
    
    scoreList = api.user_scores(user_id, "recent", include_fails=True, mode="osu", limit=10, offset=0)

    # check no recent score
    if len(scoreList) == 0:
        return "User " + user_name + " does not have a recent play on bancho!"
    
    return ("None pp on " if scoreList[0].pp == None else "{:.2f}".format(scoreList[0].pp) + "pp on ") + \
            scoreList[0].beatmapset.title + " +" + \
            str(scoreList[0].mods) + ", " + \
            "{:.2f}".format(scoreList[0].accuracy * 100) + "%, " + \
            str(scoreList[0].max_combo) + "x"
           

from discord import Client
from .tasks.time import taskTime

def startAllTasks(client: Client):
    taskTime.start(client)    

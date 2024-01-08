# MidBot - discord bot for osu!

Discord IRC bot made in python

still in startup stage

Jump to:
1. [Deploying your own bot](#deploying-your-own-bot)


## Deploying your own bot

0. Make sure you have your token for discord bot ready.

    If you have not done so, you can follow the instructions [here](https://discordpy.readthedocs.io/en/stable/discord.html).


1. Install the requirements

    Make sure you have installed pip in your local environment, and then run:

    ```bash
    pip install -r requirements.txt
    ```

    This would automatically install all the dependencies of the bot.


2. Create your new config file.

    Within your environment, you can create a config file such as ".env.midc".

    In your config file, you want to have all the parameters in .env.example set to your own parameters.


3. Link your config file with the program.

    In main.py, line 5, modify ".env.example" to be the name of the config file you just created.


4. Run the bot

    ```bash
    python3 main.py
    ```



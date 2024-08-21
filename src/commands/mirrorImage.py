from discord import Interaction, Attachment, File
from discord.ext.commands import Context
from ..bot import bot
import io
# import requests

@bot.tree.command(description='Attach a jpeg or png file to mirror it')
async def mirror_image(interaction: Interaction, image: Attachment):
    await interaction.response.defer(thinking=True)

    if image.content_type not in ["image/jpeg", "image/png"]:
        await interaction.edit_original_response(content='The file is not in jpeg or png format')
        return
    
    try:
        # response = requests.get('https://i.postimg.cc/N0txryxh/dummy-image.jpg')
        # response.raise_for_status()
        img_bytes = io.BytesIO(await image.read())
        # img_bytes.seek(0)
        file = File(img_bytes, filename='image.jpg')
        await interaction.edit_original_response(content='dummy image', attachments=[file])
    except:
        await interaction.edit_original_response(content='failed')

    

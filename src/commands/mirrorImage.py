from discord import Interaction, Attachment, File
from discord.ext.commands import Context
from ..bot import bot
import io
from PIL import Image
# import requests

def __mirror(image: Image.Image, name: str) -> File:
    width, height = image.size

    left_half = image.crop((0, 0, width//2, height))
    mirrored_left_half = left_half.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    new_image = Image.new('RGB', (width-1, height))
    new_image.paste(left_half, (0, 0))
    new_image.paste(mirrored_left_half, (width//2, 0))

    new_image_bytes = io.BytesIO()
    new_image.save(new_image_bytes, format=image.format)
    new_image_bytes.seek(0)


    return File(new_image_bytes, filename=name)

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
        # file = File(img_bytes, filename='image.jpg')
        # await interaction.edit_original_response(content='dummy image', attachments=[file])
        formatted_image = Image.open(img_bytes)
        await interaction.edit_original_response(content='Mirrored respective to the left half!', attachments=[__mirror(formatted_image, image.filename)])
    except:
        await interaction.edit_original_response(content='failed')

    

from discord import Interaction, Attachment, File
from discord.ext.commands import Context
from ..bot import bot
import io
from enum import Enum
from PIL import Image, ImageSequence
# import requests

class FlipDir(Enum):
    LEFT = 'left'
    RIGHT = 'right'
    TOP = 'top'
    BOTTOM = 'bottom'

def __mirrorFrame(image: Image.Image, dir: FlipDir) -> Image.Image:
    width, height = image.size
    new_image = Image.new('RGBA', (width-1, height-1))
    if dir == FlipDir.LEFT:
        half = image.crop((0, 0, width//2, height))
        mirrored_half = half.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        new_image.paste(half, (0, 0))
        new_image.paste(mirrored_half, (width//2, 0))

    elif dir == FlipDir.RIGHT:
        half = image.crop((width//2, 0, width, height))
        mirrored_half = half.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        new_image.paste(mirrored_half, (0, 0))
        new_image.paste(half, (width//2, 0))

    elif dir == FlipDir.TOP:
        half = image.crop((0, 0, width, height//2))
        mirrored_half = half.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        new_image.paste(half, (0, 0))
        new_image.paste(mirrored_half, (0, height//2))
    
    elif dir == FlipDir.BOTTOM:
        half = image.crop((0, height//2, width, height))
        mirrored_half = half.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        new_image.paste(mirrored_half, (0, 0))
        new_image.paste(half, (0, height//2))

    return new_image

def __mirror(image: Image.Image, name: str, dir: FlipDir) -> File:
    width, height = image.size
    new_image = Image.new('RGBA', (width-1, height-1))
    if dir == FlipDir.LEFT:
        half = image.crop((0, 0, width//2, height))
        mirrored_half = half.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        new_image.paste(half, (0, 0))
        new_image.paste(mirrored_half, (width//2, 0))

    elif dir == FlipDir.RIGHT:
        half = image.crop((width//2, 0, width, height))
        mirrored_half = half.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        new_image.paste(mirrored_half, (0, 0))
        new_image.paste(half, (width//2, 0))

    elif dir == FlipDir.TOP:
        half = image.crop((0, 0, width, height//2))
        mirrored_half = half.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        new_image.paste(half, (0, 0))
        new_image.paste(mirrored_half, (0, height//2))
    
    elif dir == FlipDir.BOTTOM:
        half = image.crop((0, height//2, width, height))
        mirrored_half = half.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        new_image.paste(mirrored_half, (0, 0))
        new_image.paste(half, (0, height//2))

    new_image_bytes = io.BytesIO()
    new_image.save(new_image_bytes, format=image.format)
    new_image_bytes.seek(0)


    return File(new_image_bytes, filename=name)

def __mirrorGif(image: Image.Image, name: str, dir: FlipDir) -> File:
    # Mirror all frames
    frames = []
    for frame in ImageSequence.Iterator(image):
        frame = frame.convert('RGBA')
        mirrored_frame = __mirrorFrame(frame, dir)
        frames.append(mirrored_frame)

    # Save those frames into a GIF
    new_gif_bytes = io.BytesIO()
    frames[0].save(new_gif_bytes, format='GIF', save_all=True, append_images=frames[1:], loop=0)
    new_gif_bytes.seek(0)

    return File(new_gif_bytes, filename=name)


@bot.tree.command(description='Attach a jpeg, png, or gif file to mirror it')
async def mirror_image(interaction: Interaction, image: Attachment, respective: FlipDir = FlipDir.LEFT):
    await interaction.response.defer(thinking=True)

    if image.content_type not in ["image/jpeg", "image/png", "image/gif"]:
        await interaction.edit_original_response(content=f'File format incorrect: attached {image.content_type}')
        return
    
    try:
        # response = requests.get('https://i.postimg.cc/N0txryxh/dummy-image.jpg')
        # response.raise_for_status()
        img_bytes = io.BytesIO(await image.read())
        # img_bytes.seek(0)
        # file = File(img_bytes, filename='image.jpg')
        # await interaction.edit_original_response(content='dummy image', attachments=[file])
        formatted_image = Image.open(img_bytes)
        if image.content_type == "image/gif":
            await interaction.edit_original_response(content=f"Mirrored respective to the {respective.value} half!", attachments=[__mirrorGif(formatted_image, image.filename, respective)])
        else:
            await interaction.edit_original_response(content=f"Mirrored respective to the {respective.value} half!", attachments=[__mirror(formatted_image, image.filename, respective)])
    except:
        await interaction.edit_original_response(content='failed')

    

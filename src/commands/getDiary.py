from discord import Interaction, Attachment, File
from ..bot import bot
from datetime import datetime
import io

@bot.tree.command()
async def export_diary(interaction: Interaction):
    await interaction.response.defer(thinking=True)
    # Extract diary Content into a string
    diaryContent = ""
    async for msg in interaction.channel.history(limit=None):
        # Check if msg is plain text
        if len(msg.attachments) != 0 \
            or len(msg.embeds) != 0 \
            or msg.content.strip() != "" \
            or msg.author != interaction.user:
            continue
        
        # Check if first line of msg is in correct format YYYY.MM.DD
        try:
            datetime.strptime(msg.content.strip()[0], "%Y.%m.%d")
        except ValueError:
            continue
        
        diaryContent += msg.content + "\n"
    
    diaryObj = io.StringIO(diaryContent)
    byteFile = io.BytesIO(diaryObj.getvalue().encode())
    diaryFile = File(byteFile, filename=f"Diary_{datetime.now().strftime("%Y%m%d")}.txt")

    await interaction.edit_original_response(content=f"Exported diary up to {datetime.now().strftime("%Y-%m-%d")}",
                                             attachments=[diaryFile])



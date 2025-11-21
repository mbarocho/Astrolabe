from discord.ui.button import View
from discord import ui
import discord
from typing import Optional, List
from eventModal import AddEventModal

class ButtonMenu(View):
    @ui.button(label="Add Event", style=discord.ButtonStyle.primary)
    async def add_event(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(view=AddEventModal(), ephemeral=True)

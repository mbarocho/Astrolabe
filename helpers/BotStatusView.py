import discord
from discord.ui import Modal, TextInput
from datetime import datetime
import pytz
from calendarModal import get_upcoming_events
from droid import GUILD_FORUM_CHANNELS
from eventModal import AddEventModal
from helpers.events import create_discord_event, create_forum_post

db_pool = None

# Control Panel
class BotStatusView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.db_pool = db_pool
        self.GUILD_FORUM_CHANNELS = GUILD_FORUM_CHANNELS

    @discord.ui.button(label="Add Event", style=discord.ButtonStyle.green)
    async def add_event_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AddEventModal(db_pool=self.db_pool, GUILD_FORUM_CHANNELS=self.GUILD_FORUM_CHANNELS)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="View Calendar", style=discord.ButtonStyle.primary)
    async def view_calendar_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Fetch the upcoming events
            events_message = await get_upcoming_events(self.db_pool, interaction.guild.id)

            # Create the embed with the events
            embed = discord.Embed(
                title="Upcoming Events",
                description=events_message,
                color=discord.Color.blue()
            )

            # Send the embed with the buttons
            await interaction.response.send_message(embed=embed, view=self)
            print("Embed sent successfully.")

        except Exception as e:
            print(f"Error sending embed: {e}")
            await interaction.followup.send("There was an error sending the calendar.", ephemeral=True)
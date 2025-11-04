import discord
from discord.ui import Modal, TextInput
from datetime import datetime, timedelta, timezone
import pytz
from helpers.events import create_discord_event, create_forum_post

class AddEventModal(Modal):
    def __init__(self, db_pool, GUILD_FORUM_CHANNELS):
        super().__init__(title="Add Event")

        self.db_pool = db_pool
        self.GUILD_FORUM_CHANNELS = GUILD_FORUM_CHANNELS

        # Define the fields (can customize label, style, placeholder, etc.)
        self.title_input = TextInput(label="Event Title", placeholder="Movie Night", max_length=100)
        self.date_input = TextInput(label="Date (MM/DD/YYYY)", placeholder="11/15/2025")
        self.time_input = TextInput(label="Time (HH:MM AM/PM)", placeholder="7:30 PM")
        self.location_input = TextInput(label="Location", placeholder="Main Voice Channel")
        self.description_input = TextInput(
            label="Description", 
            style=discord.TextStyle.paragraph, 
            placeholder="Describe the event..."
        )

        # Add inputs to the modal
        self.add_item(self.title_input)
        self.add_item(self.date_input)
        self.add_item(self.time_input)
        self.add_item(self.location_input)
        self.add_item(self.description_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        title = self.title_input.value
        date = self.date_input.value
        time = self.time_input.value
        location = self.location_input.value
        description = self.description_input.value

        guild_id = interaction.guild.id
        guild = interaction.guild
        channel = interaction.channel

        # Parse datetime
        try:
            event_datetime = datetime.strptime(f"{date} {time}", "%m/%d/%Y %I:%M %p")
            est = pytz.timezone("America/New_York")
            event_datetime_est = est.localize(event_datetime.replace(tzinfo=None))
        except ValueError:
            await interaction.followup.send(
                "Invalid date or time format. Please use MM/DD/YYYY and HH:MM AM/PM.",
                ephemeral=True
            )
            return

        async with self.db_pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT 1 FROM events WHERE guild_id = $1 AND title = $2", guild_id, title
            )
            if exists:
                await interaction.followup.send("That event already exists.", ephemeral=True)
                return

            await conn.execute(
                "INSERT INTO events (guild_id, title, date, location, description) VALUES ($1, $2, $3, $4, $5)",
                guild_id, title, date, location, description
            )

        try:
            # Your existing helper (assumes it’s defined elsewhere)
            await create_discord_event(guild, title, description, event_datetime_est, location, channel)

            forum_channel_id = self.GUILD_FORUM_CHANNELS.get(str(guild.id))
            if forum_channel_id:
                await create_forum_post(guild, forum_channel_id, title, description, event_datetime_est)
            else:
                await interaction.followup.send("No forum channel configured for this server.", ephemeral=True)

            await interaction.followup.send(
                f"✅ {interaction.user.mention} added **{title}** and created a Discord event!",
                ephemeral=False
            )

        except Exception as e:
            await interaction.followup.send(
                f"Event added to database, but failed to create Discord event:\n```{e}```",
                ephemeral=True
            )
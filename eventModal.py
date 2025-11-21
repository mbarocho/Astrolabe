import discord
from discord.ui import Modal, TextInput
from datetime import datetime
import pytz

from helpers.events import create_discord_event, create_forum_post

db_pool = None

class AddEventModal(Modal):
    def __init__(self, db_pool, GUILD_FORUM_CHANNELS):
        super().__init__(title="Add Event")

        self.db_pool = db_pool
        self.GUILD_FORUM_CHANNELS = GUILD_FORUM_CHANNELS

        # Define the fields (can customize label, style, placeholder, etc.)
        self.title_input = TextInput(label="Event Title", placeholder="Movie Night", max_length=100)
        self.date_input = TextInput(label="Date (MM/DD/YYYY)", placeholder="01/01/1970")
        self.time_input = TextInput(label="Time (HH:MM AM/PM - HH:MM AM/PM)", placeholder="12:00 AM - 01:00 AM (Please add both start and end time)")
        self.location_input = TextInput(label="Location", placeholder="Times Square - New York, NY")
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
        await interaction.response.defer(thinking=True)
        title = self.title_input.value
        date = self.date_input.value
        time = self.time_input.value
        location = self.location_input.value
        description = self.description_input.value

        guild_id = interaction.guild.id
        guild = interaction.guild
        channel = interaction.channel

        # Split start and end time
        try:
            start_time, end_time = [t.strip() for t in time.split("-")]
        except ValueError:
            await interaction.followup.send(
                "Invalid time format. Please use the format: HH:MM AM/PM - HH:MM AM/PM",
                ephemeral=True
            )
            return

        # Parse datetime
        try:
            event_datetime = datetime.strptime(f"{date} {start_time}", "%m/%d/%Y %I:%M %p")
            est = pytz.timezone("America/New_York")
            event_datetime_est = est.localize(event_datetime.replace(tzinfo=None))
        except ValueError:
            await interaction.followup.send(
                "Invalid date or time format. Please use MM/DD/YYYY and HH:MM AM/PM.",
                ephemeral=True
            )
            return

        # Check if event already exists in the database
        try:
            async with self.db_pool.acquire() as conn:
                exists = await conn.fetchval(
                    "SELECT 1 FROM events WHERE guild_id = $1 AND title = $2", guild_id, title
                )
                if exists:
                    await interaction.followup.send("That event already exists.", ephemeral=True)
                    return

                await conn.execute(
                    "INSERT INTO events (guild_id, title, date, time, location, description) VALUES ($1, $2, $3, $4, $5, $6)",
                    guild_id, title, date, time, location, description
                )
        except Exception as e:
            await interaction.followup.send(
                f"An error occurred while adding the event to the database: {e}",
                ephemeral=True
            )
            return

        # Create Discord event
        try:
            await create_discord_event(guild, title, description, event_datetime_est, location, channel)
        except Exception as e:
            await interaction.followup.send(
                f"Event added to database, but failed to create Discord event:\n```{e}```",
                ephemeral=True
            )
            return

        # Create forum post and send confirmation embed
        try:
            forum_channel_id = self.GUILD_FORUM_CHANNELS.get(str(guild.id))
            if forum_channel_id:
                eventThreadLink = await create_forum_post(guild, forum_channel_id, title, description, event_datetime_est)

                embed = discord.Embed(
                    title=f"Join us for {title}!",
                    description=f"**Date:** {date}\n**Time:** {start_time} - {end_time}\n**Location:** {location}\n\nDiscuss more in the forum channel: [Click Here]({eventThreadLink})",
                    color=discord.Color.dark_gold()
                )
                await interaction.followup.send(embed=embed, ephemeral=False)
            else:
                await interaction.followup.send("No forum channel configured for this server.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(
                f"Event added to database and Discord event created, but failed to create forum post:\n```{e}```",
                ephemeral=True
            )
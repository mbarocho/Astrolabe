import discord
from discord import app_commands
from discord.ui import Modal, TextInput
from datetime import datetime, timedelta, timezone
import pytz

droid = None  # This will be set when the bot is initialized

async def create_discord_event(guild, title: str, description: str, event_datetime_est, location: str, channel: discord.abc.Messageable):
    try:
        event = await guild.create_scheduled_event(
            name=f"{title}",
            description=f"{description}!",
            start_time=event_datetime_est,
            end_time=event_datetime_est + timedelta(hours=3),
            privacy_level=discord.PrivacyLevel.guild_only,
            entity_type=discord.EntityType.external,
            location=f"{location}"
        )
    except Exception as e:
        await channel.send(f"Failed to create the event due to an error: {e}")

async def create_forum_post(guild: discord.Guild, forum_channel_id: int, title: str, description: str, event_time: datetime):
    """Creates a forum post in the configured forum channel."""
    forum_channel = guild.get_channel(forum_channel_id)
    if not forum_channel:
        raise RuntimeError(f"Forum channel with ID {forum_channel_id} not found.")

    post_title = f"{title} Event Chat"
    try:
        eventThread = await forum_channel.create_thread(
            name=post_title,
            content=description
        )
        return eventThread.message.jump_url
    except Exception as e:
        raise RuntimeError(f"Failed to create forum post: {e}")
import asyncio
import os
import discord
import json
from discord.ext import commands
from dotenv import load_dotenv
from eventCatalog import *
from datetime import datetime, timedelta, timezone
import pytz
import asyncpg


intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# PostgreSQL connection pool
async def connect_to_db():
    pool = await asyncpg.create_pool(
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        database=os.getenv('POSTGRES_DB'),
        host=os.getenv('POSTGRES_HOST'),
        port=int(os.getenv("POSTGRES_PORT", 5432))
    )
    return pool

async def init_db():
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                guild_id BIGINT NOT NULL,
                title TEXT NOT NULL,
                date TEXT,
                location TEXT,
                description TEXT,
                PRIMARY KEY (guild_id, title)
            );
        """)
        print("Astrolabe is online.")
    

db_pool = None

# Discord bot instance
class droid(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.default())

    async def on_ready(self):
        global db_pool
        db_pool = await connect_to_db()
        await init_db()
        print(f'{self.user} has interfaced with PostgreSQL!')
        print(f'{self.user} has connected to Discord!')
        await self.tree.sync()

        filename = "event_catalog.json"
        if not os.path.exists(filename):
            with open(filename, "w") as json_file:
                json.dump({}, json_file)
        else:
            open_catalog()

droid = droid()

# @droid.event
@droid.tree.command(name="help", description="List commands.")
async def help(interaction: discord.Interaction):
    message = (
        "```"
        f"1. /backlog - Load server's event backlog.\n"
        f"2. /add - Add events to the server.\n"
        f"3. /remove - Remove events from the server.\n"
        f"4. /search - Search for content in the server's event backlog.\n"
        f"5. /help - Lists commands used by EventBot.\n"
        "```"
    )
    await interaction.response.send_message(message)

# Commands Setup
@droid.tree.command(name="backlog", description="Load server's event backlog.")
# Output Backlog in Discord
async def load(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    async with db_pool.acquire() as conn:
        # Fetch backlog from the database
        rows = await conn.fetch("SELECT title, date, location, description FROM events WHERE guild_id = $1", guild_id)
    if not rows:
        await interaction.response.send_message("Backlog is empty. Please add content to be displayed.", ephemeral=True)
        return
    message = ""
    for row in rows:
        message += (
            f"**{row['title']}** ({row['date']})\n"
            f"{row['description']}\n"
            f"Location: {row['location']}\n"
        )
    # Discord message size limit is 2000 characters, so split if necessary
    if len(message) > 2000:
        # Split the message into chunks of max 2000 characters
        for chunk in [message[i:i+2000] for i in range(0, len(message), 2000)]:
            await interaction.followup.send(chunk)  # Send follow-up message for each chunk
    else:
        await interaction.response.send_message(message)

@droid.tree.command(name="add", description="Add events to the server.")
# Add to backlog via Discord
async def add(interaction: discord.Interaction, 
              title: str, 
              date: str, 
              time: str,
              location: str,
              description: str, 
    ):
    guild_id = interaction.guild.id
    guild = interaction.guild
    channel = interaction.channel

    try:
        event_datetime = datetime.strptime(f"{date} {time}", "%m/%d/%Y %I:%M %p")
        est = pytz.timezone("America/New_York")
        event_datetime_est = est.localize(event_datetime)
    except ValueError:
        await interaction.followup.send("Invalid date or time format. Please use MM/DD/YYYY and HH:MM AM/PM.", ephemeral=True)
        return

    async with db_pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT 1 FROM events WHERE guild_id = $1 AND title = $2", guild_id, title
        )
        if exists:
            await interaction.response.send_message("This item is already in the event list.")
            return
        await conn.execute(
            "INSERT INTO events (guild_id, title, date, location, description) VALUES ($1, $2, $3, $4, $5)",
            guild_id, title, date, location, description
        )
        
        
    try:
        await create_discord_event(guild, title, description, event_datetime_est, location, channel)
        await interaction.response.send_message(
            f"{interaction.user.mention} added **{title}** and created a Discord event!",
            ephemeral=False
        )
    except Exception as e:
        await interaction.response.send_message(
            f"Event added to the database, but failed to create Discord event: {e}",
            ephemeral=True
        )

@droid.tree.command(name="remove", description="Remove content from the server's event list.")
async def remove(interaction: discord.Interaction, query: str):
    guild_id = interaction.guild.id
    async with db_pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM events WHERE guild_id = $1 AND LOWER(title) = $2",
            guild_id, query.lower()
        )
    if result and "DELETE 1" in result:
        await interaction.response.send_message(f"{interaction.user} removed **{query}** from the event list.")
    else:
        await interaction.response.send_message(f"*'{query}'* is not in the event list.")

@droid.tree.command(name="search", description="Search for events in the server's event list.")
# Search event list via Discord
async def search(interaction: discord.Interaction, query: str):
    guild_id = interaction.guild.id
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT title, location, date, description FROM events WHERE guild_id = $1", guild_id
        )
    if not rows:
        await interaction.response.send_message(
            "Event list is empty. Please add content for the bot to select content.",
            ephemeral=True
        )
        return

    message = ""
    for item in rows:
        message += (
            f"{item['title']}\n"
            f"Date: {item['date']}\n"
            f"Location: {item['location']}\n"
            f"Description: {item['description']}\n"
        )

    if len(message) > 2000:
        for chunk in [message[i:i+2000] for i in range(0, len(message), 2000)]:
            await interaction.followup.send(chunk)
    else:
        await interaction.response.send_message(message)

@droid.tree.command(name="event", description="Create event in server.")
# Create event via Discord
async def event(interaction: discord.Interaction, title: str, date: str, time: str):
    yes_emoji = '👍'
    no_emoji = '👎'
    guild_id = interaction.guild.id

    await interaction.response.defer()

    # Check if the title exists in the event list for this guild
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT title FROM events WHERE guild_id = $1 AND LOWER(title) = $2",
            guild_id, title.lower()
        )
    if not row:
        await interaction.followup.send(f"*'{title}'* is not in the event list.", ephemeral=True)
        return

    vote_message = await interaction.followup.send(
        f"{interaction.user.name} is proposing **{title}** on {date} at {time}!  React with {yes_emoji} or {no_emoji}!"
    )
    await vote_message.add_reaction(yes_emoji)
    await vote_message.add_reaction(no_emoji)

    try:
        event_datetime = datetime.strptime(f"{date} {time}", "%m/%d/%Y %I:%M %p")
        est = pytz.timezone("America/New_York")
        event_datetime_est = est.localize(event_datetime)
    except ValueError:
        await interaction.followup.send("Invalid date or time format. Please use MM/DD/YYYY and HH:MM AM/PM.", ephemeral=True)
        return

    await handle_event_voting(vote_message, title, event_datetime_est, interaction.guild, interaction.channel)
    return

async def create_discord_event(guild, title: str, description: str, event_datetime_est, location: str, channel: discord.abc.Messageable):
    try:
        # Create the scheduled event in the guild
        event = await guild.create_scheduled_event(
            name=f"{title}",
            description=f"{description}!",
            start_time=event_datetime_est,
            end_time=event_datetime_est + timedelta(hours=3),
            privacy_level=discord.PrivacyLevel.guild_only,
            entity_type=discord.EntityType.external,
            location=f"{location}"
        )
        await channel.send(f"Join us in **{title}** on {event_datetime_est.strftime('%m/%d/%Y at %I:%M %p')}!" + f" [Event Link]({event.url})")
    except Exception as e:
        await channel.send(f"Failed to create the event due to an error: {e}") 

droid.run(TOKEN)
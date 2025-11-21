import os
import discord
import json
from discord.ext import commands
from dotenv import load_dotenv
from eventCatalog import *
import datetime
import pytz
import asyncpg
from eventModal import AddEventModal
from calendarModal import get_upcoming_events


intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

with open("event_forum_channels.json", "r") as f:
    GUILD_FORUM_CHANNELS = json.load(f)

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


async def send_status_panel(guild, channel_id, message_id=None):
    channel = guild.get_channel(channel_id)
    if not channel:
        return None

    embed = discord.Embed(
        title="Astrolabe Control Panel",
        description="Astrolabe is **Online**.",
        color=discord.Color.green()
    )

    view = BotStatusView()

    if message_id:
        try:
            msg = await channel.fetch_message(message_id)
            await msg.edit(embed=embed, view=view)
            return msg.id
        except:
            pass

    # Create a fresh message
    msg = await channel.send(embed=embed, view=view)
    return msg.id


# Discord bot instance
class droid(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.default())

    async def on_ready(self):
        global db_pool
        db_pool = await connect_to_db()
        await init_db()
        print(f'{self.user} has interfaced with PostgreSQL and connected to Discord!')
        await self.tree.sync()

        for guild in self.guilds:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT guild_id, status_channel_id, status_message_id FROM guild_settings WHERE guild_id = $1",
                    guild.id
                )

            channel_id = row["status_channel_id"] if row else (guild.system_channel.id if guild.system_channel else None)
            if not channel_id:
                continue

            message_id = row["status_message_id"] if row else None
            new_msg_id = await send_status_panel(guild, channel_id, message_id)

            async with db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO guild_settings (guild_id, status_channel_id, status_message_id)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (guild_id) DO UPDATE
                    SET status_channel_id = EXCLUDED.status_channel_id,
                        status_message_id = EXCLUDED.status_message_id
                """, guild.id, channel_id, new_msg_id)

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
        f"1. /calendar - Load server's event calendar.\n"
        f"2. /add - Add events to the server.\n"
        f"3. /remove - Remove events from the server.\n"
        f"4. /search - Search for content in the server's event calendar.\n"
        f"5. /help - Lists commands used by EventBot.\n"
        "```"
    )
    await interaction.response.send_message(message)

# Commands Setup
@droid.tree.command(name="calendar", description="Load server's event calendar.")
async def load(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT title, date, time, location, description FROM events WHERE guild_id = $1", guild_id)
    if not rows:
        await interaction.response.send_message("calendar is empty. Please add content to be displayed.", ephemeral=True)
        return
    message = ""
    for row in rows:
        message += (
            f"**{row['title']}** ({row['date']})\n"
            f"Time: {row['time']}\n"
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
# Add to calendar via Discord
async def add(interaction: discord.Interaction):
    modal = AddEventModal(db_pool=db_pool, GUILD_FORUM_CHANNELS=GUILD_FORUM_CHANNELS)
    await interaction.response.send_modal(modal)

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
            "SELECT title, location, date, time, description FROM events WHERE guild_id = $1", guild_id
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
            f"Time: {item['time']}\n"
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
    return

async def create_forum_post(guild, forum_channel_id: int, title: str, description: str, event_datetime_est):
    forum_channel = droid.get_channel(forum_channel_id)
    try:
        thread = await forum_channel.create_thread(
            name=title,
            content=f"Discussion thread for **{title}** happening on {event_datetime_est.strftime('%m/%d/%Y at %I:%M %p')}!\n\n{description}",
            reason="Discussion for the upcoming event."
        )
    except Exception as e:
        await forum_channel.send(f"Failed to create the discussion thread due to an error: {e}")

droid.run(TOKEN)
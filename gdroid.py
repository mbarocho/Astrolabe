import os
import discord
import json
from discord.ext import commands
from dotenv import load_dotenv
from eventCatalog import *
import asyncio
from eventModal import AddEventModal
from calendarModal import get_upcoming_events
import gspread



intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
SPREADSHEET_NAME = "Astrolabe Event Catalog"
WORKSHEET_NAME = "Events"

gc = gspread.service_account(filename=os.getenv("GSHEETS_CREDENTIALS_FILE"))

def get_events_worksheet():
    spreadsheet = gc.open(SPREADSHEET_NAME)
    worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
    return worksheet

with open("event_forum_channels.json", "r") as f:
    GUILD_FORUM_CHANNELS = json.load(f)

events_worksheet = None

# Control Panel
class BotStatusView(discord.ui.View):
    def __init__(self, event_repository, GUILD_FORUM_CHANNELS):
        super().__init__(timeout=None)
        self.event_repository = event_repository
        self.GUILD_FORUM_CHANNELS = GUILD_FORUM_CHANNELS

    @discord.ui.button(label="Add Event", style=discord.ButtonStyle.green)
    async def add_event_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AddEventModal(event_repository=self.event_repository, GUILD_FORUM_CHANNELS=self.GUILD_FORUM_CHANNELS)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="View Calendar", style=discord.ButtonStyle.primary)
    async def view_calendar_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Fetch the upcoming events
            events_message = await get_upcoming_events(self.event_repository, interaction.guild.id)

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


async def send_status_panel(guild, channel_id, event_repository, guild_forum_channels, message_id=None):
    channel = guild.get_channel(channel_id)
    if not channel:
        return None

    embed = discord.Embed(
        title="Astrolabe Control Panel",
        description="Astrolabe is **Online**.",
        color=discord.Color.green()
    )

    view = BotStatusView(event_repository, guild_forum_channels)
    
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
class gdroid(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.default())
        self.event_repository = None
        self.GUILD_FORUM_CHANNELS = GUILD_FORUM_CHANNELS

    async def on_ready(self):
        events_worksheet = await asyncio.to_thread(get_events_worksheet)
        self.event_repository = GoogleSheetsEventRepository(events_worksheet)
        print(f'{self.user} has interfaced with Google Sheets and connected to Discord!')
        await self.tree.sync()

        def get_guild_worksheet(spreadsheet, guild_id):
            title = f"guild_{guild_id}"

            try:
                return spreadsheet.worksheet(title)
            except gspread.WorksheetNotFound:
                return spreadsheet.add_worksheet(
                    title=title,
                    rows=1000,
                    cols=10
                )

        for guild in self.guilds:
            target_channel = discord.utils.get(guild.text_channels, name="astrolabe")
            if target_channel:
                channel_id = target_channel.id
            else:
                channel_id = (
                    guild.system_channel.id
                    if guild.system_channel
                    else next(
                        (ch.id for ch in guild.text_channels), None
                    )
                )

            if not channel_id:
                print(f"Warning: Guild {guild.name} has no text channel named 'astrolabe'. Skipping.")
                continue

            await send_status_panel(guild, channel_id, self.event_repository, self.GUILD_FORUM_CHANNELS)

        self._init_local_catalog()

    @staticmethod
    def _init_local_catalog():
        filename = "event_catalog.json"
        if not os.path.exists(filename):
            with open(filename, "w") as f:
                json.dump({}, f)
        else:
            open_catalog()

async def _send_long_message(interaction, message: str):
    if len(message) <= 2000:
        await interaction.response.send_message(message)
        return

    for chunk in (
        message[i:i + 2000]
        for i in range(0, len(message), 2000)
    ):
        await interaction.followup.send(chunk)

class GoogleSheetsEventRepository:
    def __init__(self, ws):
        self.ws = ws

    async def get_all(self, guild_id):
        rows = await asyncio.to_thread(self.ws.get_all_records)
        filtered = []
        guild_id_str = str(guild_id)
        for r in rows:
            raw_gid = r.get("guild_id")
            if raw_gid is None:
                continue

            gid_str = str(raw_gid).strip()
    
            if gid_str == guild_id_str:
                filtered.append(r)

        print(f"Filtered rows for guild {guild_id_str}:", filtered)
        return filtered

    async def add(self, event: dict):
        event_copy = event.copy()
        event_copy["guild_id"] = str(event_copy["guild_id"])
        await asyncio.to_thread(self.ws.append_row, list(
            [
                event_copy["guild_id"],
                event_copy["title"],
                event_copy["date"],
                event_copy["time"],
                event_copy["location"],
                event_copy["description"]
            ]
        ))

    async def remove(self, guild_id: int, title: str) -> bool:
        guild_id_str = str(guild_id)
        rows = await asyncio.to_thread(self.ws.get_all_records)
        for idx, row in enumerate(rows, start=2):
            row_gid = str(int(float(row.get("guild_id", 0)))) if row.get("guild_id") else ""
            if row_gid == guild_id_str and row["title"].lower() == title.lower():
                await asyncio.to_thread(self.ws.delete_rows, idx)
                return True
        return False

    async def exists(self, guild_id: int, title: str) -> bool:
        rows = await self.get_all(guild_id)
        title_lower = title.lower()
        return any(
            str(r.get("title", "")).lower() == title_lower
            for r in rows
        )
    
gdroid = gdroid()

@gdroid.tree.command(name="calendar", description="Load server's event calendar.")
async def calendar(interaction: discord.Interaction):
    guild_id = interaction.guild.id

    events = await interaction.client.event_repository.get_all(guild_id)

    if not events:
        await interaction.response.send_message(
            "The calendar is empty.",
            ephemeral=True
        )
        return

    message = ""
    for e in events:
        message += (
            f"**{e['title']}** ({e['date']})\n"
            f"Time: {e['time']}\n"
            f"Location: {e['location']}\n"
            f"{e['description']}\n\n"
        )

    await _send_long_message(interaction, message)

gdroid.run(TOKEN)
import discord
from discord.ui import Modal, TextInput
import datetime

db_pool = None

async def get_upcoming_events(db_pool, guild_id):
    """Fetch upcoming events and format them as a string."""
    today = datetime.datetime.now().date()
    time = datetime.datetime.now().time()

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT title, date, time, location, description FROM events WHERE guild_id = $1 AND (date > $2 OR (date = $2 AND time > $3)) ORDER BY date ASC, time ASC",
            guild_id,
            today.strftime("%m-%d-%Y"),
            time.strftime("%I:%M %p")
        )

    events_message = ""
    if not rows:
        events_message = "No upcoming events."
    else:
        for row in rows:
            event_date = row['date']  # Format the date as necessary
            event_time = row['time']  # Format the time as necessary
            events_message += f"**{row['title']}** - {event_date}, {event_time}\n"
            events_message += f"Location: {row['location']}\n"
            events_message += f"Description: {row['description']}\n\n"

    return events_message
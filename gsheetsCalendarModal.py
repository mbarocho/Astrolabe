import asyncio
import datetime

DATE_FORMAT = "%m-%d-%Y"
TIME_FORMAT = "%I:%M %p"

async def get_upcoming_events(event_repository, guild_id: int):
    """Fetch upcoming events and format them as a string."""
    now = datetime.datetime.now()
    today = now.date()
    time = now.time()

    events = await asyncio.to_thread(event_repository.get_all, guild_id)

    upcoming_events = []
    for event in events:
        try:
            event_date = datetime.datetime.strptime(event['date'], DATE_FORMAT).date()
            event_time = datetime.datetime.strptime(event['time'], TIME_FORMAT).time()
        except (ValueError, KeyError):
            continue

        if event_date > today or (event_date == today and event_time >= time):
            upcoming_events.append((event_date, event_time, event))

    upcoming_events.sort(key=lambda x: (x[0], x[1]))

    if not upcoming_events:
        return "No upcoming events."
    
    message = ""
    for _, _, event in upcoming_events:
        message += (
            f"**{event['title']}** - {event['date']}, {event['time']}\n"
            f"Location: {event['location']}\n"
            f"Description: {event['description']}\n\n"
        )
    return message
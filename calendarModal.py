import datetime
import asyncio

async def get_upcoming_events(event_repository, guild_id):
    """
    Fetch upcoming events for a guild from Google Sheets.
    Returns a formatted string.
    """
    # Fetch all events for the guild
    rows = await event_repository.get_all(guild_id)

    if not rows:
        return "No upcoming events."

    today = datetime.datetime.now().date()
    now_time = datetime.datetime.now().time()

    upcoming_rows = []

    for row in rows:
        # Parse the date
        raw_date = row.get("date")
        if not raw_date:
            continue

        parsed_date = None
        for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y"):
            try:
                parsed_date = datetime.datetime.strptime(raw_date, fmt).date()
                break
            except Exception:
                continue

        if parsed_date is None:
            continue  # skip if date can't be parsed

        # Parse the start and end times
        start_time_str, end_time_str = None, None
        start_time_obj, end_time_obj = datetime.time.min, datetime.time.min

        try:
            times = row.get("time", "").split("-")
            if len(times) == 2:
                start_time_str, end_time_str = times
                start_time_obj = datetime.datetime.strptime(start_time_str.strip(), "%I:%M %p").time()
                end_time_obj = datetime.datetime.strptime(end_time_str.strip(), "%I:%M %p").time()
        except Exception:
            pass  # defaults already set to 00:00 if parsing fails

        # Only include future events (today's events must be later than now)
        if parsed_date > today or (parsed_date == today and start_time_obj >= now_time):
            upcoming_rows.append((parsed_date, start_time_obj, row))

    if not upcoming_rows:
        return "No upcoming events."

    # Sort by date, then start time
    upcoming_rows.sort(key=lambda x: (x[0], x[1]))

    # Build message
    events_message = ""
    for date_obj, start_time_obj, row in upcoming_rows:
        events_message += (
            f"**{row['title']}** - {row['date']}, {row.get('time', 'N/A')}\n"
            f"Location: {row.get('location', 'N/A')}\n"
            f"Description: {row.get('description', 'N/A')}\n\n"
        )
        
    return events_message.strip()
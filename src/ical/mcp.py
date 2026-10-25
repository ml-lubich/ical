import sys
import json
import asyncio
import datetime
from typing import List, Optional
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    from mcp.server.mcpserver import MCPServer as FastMCP
from ical.calendar import (
    add_event as core_add_event,
    date_window,
    delete_event as core_delete_event,
    edit_event as core_edit_event,
    get_event_details as core_get_event_details,
    get_events as core_get_events,
    search_events as core_search_events,
    run_applescript,
)

mcp = FastMCP("ical")

@mcp.tool()
def list_calendars() -> List[str]:
    """List available calendars in macOS Calendar.app."""
    script = 'tell application "Calendar" to get name of calendars'
    return run_applescript(script).split(", ")

@mcp.tool()
def list_events(
    calendar: str = "Calendar",
    date: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> List[dict]:
    """List calendar events with IDs and locations, optionally restricted to a date window."""
    if date is not None and (from_date is not None or to_date is not None):
        raise ValueError("date cannot be combined with from_date or to_date")
    if (from_date is None) != (to_date is None):
        raise ValueError("from_date and to_date must be provided together")
    if date is not None:
        window_start, window_end = date_window(date, date)
        events = core_get_events(calendar, start_before=window_end, end_after=window_start)
    elif from_date is not None and to_date is not None:
        window_start, window_end = date_window(from_date, to_date)
        events = core_get_events(calendar, start_before=window_end, end_after=window_start)
    else:
        events = core_get_events(calendar)
    return [
        {
            "id": e.get("id", ""),
            "title": e["title"],
            "start": e["start_str"],
            "end": e["end_str"],
            "location": e.get("location", ""),
        } for e in events
    ]


@mcp.tool()
def search_events(
    query: str,
    calendar: str = "Calendar",
    date: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = 20,
) -> List[dict]:
    """Search event titles and locations, optionally within a local date window."""
    if date is not None and (from_date is not None or to_date is not None):
        raise ValueError("date cannot be combined with from_date or to_date")
    if (from_date is None) != (to_date is None):
        raise ValueError("from_date and to_date must be provided together")
    kwargs = {}
    if date is not None:
        window_start, window_end = date_window(date, date)
        kwargs = {"start_before": window_end, "end_after": window_start}
    elif from_date is not None and to_date is not None:
        window_start, window_end = date_window(from_date, to_date)
        kwargs = {"start_before": window_end, "end_after": window_start}
    events = core_search_events(query, calendar, limit=limit, **kwargs)
    return [
        {
            "id": event.get("id", ""),
            "title": event["title"],
            "start": event["start_str"],
            "end": event["end_str"],
            "location": event.get("location", ""),
        }
        for event in events
    ]


@mcp.tool()
def show_event(calendar: str, event_id: str) -> dict:
    """Read any calendar event by ID, including location, notes, URL, and attendees."""
    event = core_get_event_details(calendar, event_id)
    return {
        key: value.isoformat() if isinstance(value, datetime.datetime) else value
        for key, value in event.items()
    }


@mcp.tool()
def edit_calendar_event(
    calendar: str,
    event_id: str,
    title: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    location: Optional[str] = None,
    description: Optional[str] = None,
) -> dict:
    """Edit supplied fields on one Calendar event ID and verify the result."""
    core_edit_event(
        calendar, event_id, title=title, start=start, end=end,
        location=location, description=description,
    )
    event = core_get_event_details(calendar, event_id)
    return {
        key: value.isoformat() if isinstance(value, datetime.datetime) else value
        for key, value in event.items()
    }


@mcp.tool()
def delete_calendar_event(calendar: str, event_id: str, confirm: bool = False) -> dict:
    """Delete one Calendar event by ID; set confirm=true to authorize deletion."""
    if not confirm:
        raise ValueError("Event deletion requires confirm=true")
    return core_delete_event(calendar, event_id)

@mcp.tool()
def add_calendar_event(
    title: str,
    start: str,
    end: str,
    calendar: str = "Calendar",
    attendees: Optional[List[str]] = None,
    description: str = "",
    location: str = "",
    check_conflict: bool = True
) -> dict:
    """Add a calendar event with automatic conflict detection and attendee invites."""
    try:
        return core_add_event(
            title=title,
            start=start,
            end=end,
            calendar=calendar,
            attendee=attendees,
            description=description,
            location=location,
            check_conflict=check_conflict
        )
    except ValueError as err:
        return {"error": str(err), "status": "conflict_detected"}
    except Exception as err:
        return {"error": str(err), "status": "failed"}

def run_server():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    run_server()

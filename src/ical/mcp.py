import sys
import json
import asyncio
from typing import List, Optional
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    from mcp.server.mcpserver import MCPServer as FastMCP
from ical.calendar import add_event as core_add_event, get_events as core_get_events, run_applescript

mcp = FastMCP("ical")

@mcp.tool()
def list_calendars() -> List[str]:
    """List available calendars in macOS Calendar.app."""
    script = 'tell application "Calendar" to get name of calendars'
    return run_applescript(script).split(", ")

@mcp.tool()
def list_events(calendar: str = "Calendar") -> List[dict]:
    """List events in a calendar."""
    events = core_get_events(calendar)
    return [
        {
            "title": e["title"],
            "start": e["start_str"],
            "end": e["end_str"]
        } for e in events
    ]

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

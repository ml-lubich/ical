import json

def build_schema() -> dict:
    return {
        "name": "ical",
        "description": "macOS Calendar.app CLI & MCP tool",
        "commands": {
            "calendars": {
                "description": "List available calendars",
                "args": []
            },
            "list": {
                "description": "List events in a calendar",
                "flags": {
                    "--calendar": "Calendar name (default: Calendar)",
                    "--json": "Output JSON"
                }
            },
            "add": {
                "description": "Add event with automatic conflict detection and attendee invites",
                "flags": {
                    "--title": "Event title (required)",
                    "--start": "Start time string (required)",
                    "--end": "End time string (required)",
                    "--calendar": "Calendar name",
                    "--attendee": "Email address of attendee (repeatable)",
                    "--description": "Event description",
                    "--location": "Event location",
                    "--no-check-conflict": "Disable conflict detection"
                }
            },
            "mcp": {
                "description": "Run FastMCP stdio server"
            }
        }
    }

def build_guide() -> str:
    return """# ical Agent Guide

`ical` is an LLM-native CLI tool for macOS Calendar.app.

## Common Operations:
- List calendars: `ical calendars`
- List events in calendar: `ical list -c michaelle.lubich@gmail.com --json`
- Add event with conflict check & invites:
  `ical add -t "Meeting" -s "Monday, August 10, 2026 at 1:00 PM" -e "Monday, August 10, 2026 at 2:00 PM" -c "michaelle.lubich@gmail.com" -a "user@example.com"`
- Launch FastMCP stdio server for tool calling: `ical mcp`
"""

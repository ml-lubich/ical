---
name: ical
description: Read and write macOS Calendar.app events from the CLI or from an AI agent over MCP. Use when asked to list calendars, list/check events, schedule a meeting, or check for scheduling conflicts on a Mac. Triggers include "what's on my calendar", "add an event", "schedule a meeting", "check for conflicts", "list my calendars", or any request to automate macOS Calendar.
---

# ical

CLI + MCP server for macOS Calendar.app, driven via AppleScript. List calendars, list events, and add events with attendee invites and automatic conflict detection.

## Install

Local dev copy:
```bash
uv tool install -e ~/dev/ical
```

From git (what a friend/fresh machine runs):
```bash
git clone https://github.com/ml-lubich/ical
uv tool install -e ./ical
```

Or from PyPI (package name `mac-ical`):
```bash
uv tool install mac-ical
```

## CLI commands

```
ical calendars                    # List available calendars in Calendar.app
ical list -c "Calendar" [--json]  # List events in a calendar (table or JSON)
ical add -t TITLE -s START -e END [-c CALENDAR] [-a ATTENDEE ...] \
         [-d DESCRIPTION] [-l LOCATION] [--no-check-conflict]
ical mcp                          # Run the FastMCP server over stdio
ical agent guide                  # Playbook for LLM/automation use
ical agent schema                 # JSON contract for the above
ical version
```

`add` requires `--title/-t`, `--start/-s`, `--end/-e` (natural-language dates,
e.g. `"Monday, August 10, 2026 at 1:00:00 PM"`); conflict checking is on by
default (`--check-conflict`/`--no-check-conflict`).

## MCP server

Launch command: `ical mcp` (stdio transport). Exposes 3 tools:
`list_calendars`, `list_events(calendar)`, `add_calendar_event(title, start, end, calendar, attendees, description, location, check_conflict)`.

Register with Claude Code:
```bash
claude mcp add ical -- ical mcp
```

Or manually in an MCP client config:
```json
{
  "mcpServers": {
    "ical": { "command": "ical", "args": ["mcp"] }
  }
}
```

If `ical` isn't on `PATH`, use the absolute path from `uv tool dir --bin`.

**Known limitation:** `ical list` / `list_events` can be slow on calendars with
many recurring events — this is a macOS Calendar AppleScript scripting-bridge
performance limitation, not a bug in this tool's parsing.

## macOS permissions

Every command that touches Calendar.app runs through `osascript`, which
triggers macOS's **Automation** permission: the calling app (Terminal.app,
your MCP client, etc.) needs "Allow Terminal to control Calendar" approval in
System Settings → Privacy & Security → Automation. No Full Disk Access,
Contacts, or other privacy grants are needed.

Trigger the permission prompt with a harmless read:
```bash
ical calendars
```

## Safety rules

- Read-only by default: `calendars` and `list` never modify Calendar.app.
- `add` creates a real calendar event and, with `--attendee`, sends real
  invites — only run it when the user explicitly asked for that event.
- Conflict detection is on by default; don't disable it unless asked.
- Never write automation that silently loops `add` — every event this tool
  creates is a real Calendar.app event visible to attendees.

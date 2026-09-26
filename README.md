# ical CLI

macOS Calendar.app CLI tool — schedule, invite, list, delete calendar events.

## Install
```bash
pip install mac-ical
# or
brew install ml-lubich/tap/ical
```

From a checkout:

```bash
uv tool install -e ~/dev/ical
```

## Usage
```bash
ical calendars
ical add --title "Team Sync" --start "Monday, August 10, 2026 at 1:00:00 PM" --end "Monday, August 10, 2026 at 2:00:00 PM" -a guest@example.com -c you@example.com
ical list -c you@example.com
```

## MCP (for AI agents)
`ical mcp` runs a FastMCP server over stdio exposing `list_calendars`, `list_events`, and `add_calendar_event`. Point any MCP-compatible client (Claude Desktop, Claude Code, etc.) at the installed `ical` binary:
```json
{
  "mcpServers": {
    "ical": {
      "command": "ical",
      "args": ["mcp"]
    }
  }
}
```
If `ical` isn't on `PATH`, use the absolute path (e.g. from `uv tool install`, printed as `Installed 1 executable: ical`; find it with `uv tool dir --bin`).

**Known limitation:** macOS Calendar's AppleScript scripting bridge is slow for calendars with many recurring events — `ical list`/`list_events` can take a long time (or appear to hang) on such calendars, independent of event count reported by `ical calendars`. This is a limitation of AppleScript's Calendar.app automation, not of this tool's parsing.

## Testing
```bash
uv run --extra dev pytest --cov=ical --cov-report=term-missing
```
Tests mock only the OS boundary (`subprocess`/`osascript`); parsing, conflict detection, CLI dispatch, and MCP tool functions run for real.

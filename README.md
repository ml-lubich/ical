# ical CLI

macOS Calendar.app CLI tool — schedule, invite, list, and verify calendar events.

## Install
```bash
uv tool install --python 3.14 ical-mcp
# or, with Python 3.10 or newer
pip install ical-mcp
# or
brew install ml-lubich/tap/ical
```

From a checkout:

```bash
uv tool install --editable .
```

The PyPI distribution is named `ical-mcp`. It installs the `ical` Typer CLI
and the standalone `ical-mcp` stdio server; `ical mcp` remains a compatibility
alias for the server command.

## Usage
```bash
ical -h
ical agent -h
ical calendars
ical add --title "Team Sync" --start "Monday, August 10, 2026 at 1:00:00 PM" --end "Monday, August 10, 2026 at 2:00:00 PM" -a guest@example.com -c you@example.com
ical add --title "Team Sync" --start "Monday, August 10, 2026 at 1:00:00 PM" --end "Monday, August 10, 2026 at 2:00:00 PM" -a guest@example.com -c you@example.com --json
ical show --id EVENT_ID --calendar you@example.com --json
ical list -c you@example.com
ical list -c you@example.com -j
ical list -c you@example.com --date 2026-10-27
ical list -c you@example.com --from 2026-10-27 --to 2026-10-31
```

Every command and command group accepts both `-h` and `--help`; generated
shell-completion flags are disabled so help lists the supported command
surface. `ical list` prints a human-readable table; `-j`/`--json` prints JSON
to stdout. `ical add` verifies the created event by reading it back from
Calendar before reporting success. Human output summarizes the verified event
and attendee RSVP status. With `--json`, it returns a stable object with
`status: "verified"` and an `event` containing the event ID, title, ISO 8601
start and end, calendar, and attendees (`email` and `status`). A post-write verification
failure reports `status: "created_unverified"`, along with the event ID and
error. `unknown` RSVP status means
Calendar has no recorded response from that attendee yet; it does not mean
they accepted. CLI errors are printed to stderr and return a nonzero exit
status.

`ical list` without date options lists the whole calendar. Use `--date`
(`YYYY-MM-DD`) to list one local calendar day, or use both `--from` and `--to`
for an inclusive date range. Date-filtered lists query Calendar.app only for
events overlapping that window, so they stay focused even when unrelated
events elsewhere in the calendar cannot be read. Matching events are read
individually, so one unreadable item does not hide other readable events in
the requested window. `--date` cannot be combined
with `--from` or `--to`; ranges require both endpoints. `-j`/`--json` keeps the
same `{ "calendar": ..., "events": [{ "title": ..., "start": ..., "end": ... }] }`
shape for filtered and unfiltered results.

Start and end values accept natural-language dates and ISO 8601. An explicit
ISO 8601 UTC offset is converted to the Mac's local calendar time before the
event is created; numeric date components avoid AppleScript misreading ISO
strings as locale-specific dates.

Every Calendar AppleScript call has a 20-second timeout. Conflict checks and
date-filtered `ical list` calls ask Calendar only for events that overlap the
requested time window, which avoids loading an entire large calendar. Calendar
failures, timeouts, and failed event lookups are reported as errors; `ical list`
does not turn an automation failure into an empty calendar. If creation times
out before Calendar returns an ID, JSON reports
`status: "write_outcome_unknown"`
and an error. Search for the event with `ical list` before retrying. If the
conflict check times out before creation starts, JSON reports
`status: "not_created"`; it is safe to retry after Calendar responds. If an ID
is available but read-back failed, use `ical show --id EVENT_ID --calendar
CALENDAR --json` to verify it. **Do not retry the add until confirming the
event is absent**, or you may send a duplicate invitation. `ical show` is
read-only and returns the same verified event envelope as `ical add`. A JSON
lookup failure returns `status: "verification_failed"`, the requested event
ID, and the error; retry the read after checking Calendar, never the add.

## MCP (for AI agents)
`ical-mcp` is the standalone FastMCP server command for stdio clients. It exposes `list_calendars`, `list_events`, and `add_calendar_event`. The backward-compatible `ical mcp` command runs the same server. Point any MCP-compatible client (Claude Desktop, Claude Code, etc.) at the standalone executable:
```json
{
  "mcpServers": {
    "ical": {
      "command": "ical-mcp"
    }
  }
}
```
If `ical-mcp` isn't on `PATH`, use its absolute path from `uv tool dir --bin`. Existing MCP configs using `ical` with `args: ["mcp"]` continue to work.

macOS Calendar's AppleScript scripting bridge can be slow for calendars with
many recurring events. Calls now stop after the bounded timeout and return an
actionable error instead of appearing to hang indefinitely.

## Testing
```bash
uv run --extra dev pytest
```
The default test command reports coverage and enforces an 80% minimum. Tests mock only the OS boundary (`subprocess`/`osascript`); parsing, conflict detection, CLI dispatch, and MCP tool functions run for real.

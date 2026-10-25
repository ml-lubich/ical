import json

def build_schema() -> dict:
    return {
        "name": "ical",
        "description": "macOS Calendar.app CLI and MCP tool with bounded operations and verified invite creation",
        "apple_script_timeout_seconds": 20,
        "commands": {
            "calendars": {
                "description": "List available calendars",
                "args": []
            },
            "list": {
                "description": "List events with Calendar ID and location; optionally restrict to a local date or inclusive date range",
                "flags": {
                    "--calendar": "Calendar name (default: Calendar)",
                    "--date": "List one local date (YYYY-MM-DD); cannot combine with --from/--to",
                    "--from": "Inclusive first local date (YYYY-MM-DD); requires --to",
                    "--to": "Inclusive last local date (YYYY-MM-DD); requires --from",
                    "--json": "Output JSON"
                },
                "event_fields": ["id", "title", "start", "end", "location"],
                "date_filter_semantics": "Calendar-native overlap query; --date and --from/--to use local calendar dates, range endpoints are inclusive",
                "errors": "Invalid or incomplete date filters and Calendar automation failures return errors; a Calendar failure is never returned as an empty list"
            },
            "search": {
                "description": "Find events whose title or location contains the query",
                "args": {"query": "Non-empty, case-insensitive substring (required)"},
                "flags": {
                    "--calendar": "Calendar name (default: Calendar)",
                    "--date": "Search one local date (YYYY-MM-DD); cannot combine with --from/--to",
                    "--from": "Inclusive first local date (YYYY-MM-DD); requires --to",
                    "--to": "Inclusive last local date (YYYY-MM-DD); requires --from",
                    "--limit": "Maximum results (positive integer; default: 20)",
                    "--json": "Output JSON"
                },
                "event_fields": ["id", "title", "start", "end", "location"],
                "errors": "Blank queries, invalid date filters, and Calendar automation failures return errors"
            },
            "show": {
                "description": "Read any event by Calendar ID, including events created outside ical",
                "flags": {
                    "--id": "Calendar event ID (required; can come from ical list)",
                    "--calendar": "Calendar name containing the event (default: Calendar)",
                    "--json": "Return a machine-readable verified result"
                },
                "event_fields": ["id", "title", "start", "end", "calendar", "location", "description", "url", "attendees"],
                "optional_text_fields": "location, description, and url are empty strings when Calendar has no value",
                "attendees": {"fields": ["email", "status"], "status_values": ["accepted", "declined", "tentative", "unknown"]}
            },
            "edit": {
                "description": "Edit only explicitly supplied fields on one event ID and verify them",
                "flags": {
                    "--id": "Calendar event ID (required)",
                    "--calendar": "Calendar name (default: Calendar)",
                    "--title": "Optional replacement title",
                    "--start": "Optional replacement start date and time",
                    "--end": "Optional replacement end date and time",
                    "--location": "Optional replacement location; empty value clears it",
                    "--description": "Optional replacement description; empty value clears it",
                    "--json": "Return a machine-readable verified result"
                },
                "requires_at_least_one_of": ["--title", "--start", "--end", "--location", "--description"],
                "omitted_fields": "Preserved",
                "match_policy": "Exact Calendar event ID in the selected calendar"
            },
            "delete": {
                "description": "Delete one event by Calendar ID and verify it no longer exists",
                "flags": {
                    "--id": "Calendar event ID (required)",
                    "--calendar": "Calendar name (default: Calendar)",
                    "--yes": "Required explicit confirmation",
                    "--json": "Return deleted or delete_outcome_unknown status"
                },
                "confirmation_required": True,
                "success": {"status": "deleted", "fields": ["id", "calendar"]},
                "failure": {"status": "delete_outcome_unknown", "instruction": "Inspect Calendar before retrying"}
            },
            "update": {
                "description": "Upgrade the installed ical CLI using uv",
                "command": ["uv", "tool", "upgrade", "ical-mcp"],
                "domain_data_mutation": False
            },
            "add": {
                "description": "Create an event, check for conflicts, invite attendees, then read the event back by ID before reporting success",
                "flags": {
                    "--title": "Event title (required)",
                    "--start": "Start time string (required)",
                    "--end": "End time string (required)",
                    "--calendar": "Calendar name",
                    "--attendee": "Email address of attendee (repeatable)",
                    "--description": "Event description",
                    "--location": "Event location",
                    "--no-check-conflict": "Disable conflict detection",
                    "--json": "Return a machine-readable verified result"
                }
            },
            "mcp": {
                "description": "Run FastMCP stdio server"
            }
        },
        "add_result": {
            "status": ["verified", "created_unverified", "write_outcome_unknown", "not_created"],
            "event": {
                "fields": ["id", "title", "start", "end", "calendar", "location", "description", "url", "attendees"],
                "start": "ISO 8601 string",
                "end": "ISO 8601 string",
                "optional_text_fields": ["location", "description", "url"],
                "attendees": {"fields": ["email", "status"], "status_values": ["accepted", "declined", "tentative", "unknown"]}
            },
            "unverified_fields": ["status", "id", "error"],
            "write_outcome_unknown_fields": ["status", "error"],
            "not_created_fields": ["status", "stage", "error"],
            "show_result": {
                "success": {"status": "verified", "event": "same event object as add"},
                "failure": {"status": "verification_failed", "id": "requested event ID", "error": "reason"}
            },
            "note": "Calendar attendee status describes RSVP state. An unknown status means no response is recorded; it does not mean accepted. created_unverified means the write may have succeeded but read-back failed; preserve its ID and check with `ical show`. write_outcome_unknown means event creation timed out before its ID was returned; search the calendar with `ical list` before retrying."
        },
        "mcp_tools": {
            "list_events": {
                "description": "List events with Calendar ID and location",
                "args": {
                    "calendar": "Calendar name (default: Calendar)",
                    "date": "Optional local date (YYYY-MM-DD)",
                    "from_date": "Optional inclusive first local date; requires to_date",
                    "to_date": "Optional inclusive last local date; requires from_date"
                }
            },
            "show_event": {
                "description": "Read any event by Calendar ID",
                "args": {"calendar": "Calendar name", "event_id": "Calendar event ID"},
                "event_fields": ["id", "title", "start", "end", "calendar", "location", "description", "url", "attendees"]
            },
            "edit_calendar_event": {
                "description": "Edit supplied fields on one event ID and verify the result",
                "args": ["calendar", "event_id", "title?", "start?", "end?", "location?", "description?"],
                "requires_at_least_one_of": ["title", "start", "end", "location", "description"],
                "omitted_fields": "Preserved"
            },
            "delete_calendar_event": {
                "description": "Delete one event by Calendar ID with explicit confirmation",
                "args": ["calendar", "event_id", "confirm"],
                "confirmation_value": True
            },
            "search_events": {
                "description": "Search event titles and locations; optionally restrict to a date or inclusive date range",
                "args": {
                    "query": "Non-empty, case-insensitive substring",
                    "calendar": "Calendar name (default: Calendar)",
                    "date": "Optional local date (YYYY-MM-DD)",
                    "from_date": "Optional inclusive first local date; requires to_date",
                    "to_date": "Optional inclusive last local date; requires from_date",
                    "limit": "Maximum results (positive integer; default: 20)"
                },
                "event_fields": ["id", "title", "start", "end", "location"]
            }
        },
        "errors": {
            "timeout": "Calendar automation exceeded its bounded timeout. The outcome of a write may be uncertain.",
            "created_unverified": "The event may have been created, but read-back did not confirm it. Preserve the event ID and inspect Calendar before retrying.",
            "write_outcome_unknown": "Event creation timed out before an ID was returned. The write may have succeeded. Search with `ical list`; do not retry until you confirm the event is absent.",
            "not_created": "The conflict check timed out before the event write began. No event was created; retry after Calendar responds.",
            "verification_failed": "Read-only event lookup failed. The CLI returns the event ID and error; check Calendar and retry the read, not the create.",
            "conflict": "An overlapping event was found; no event was created.",
            "calendar_error": "Calendar automation failed. The CLI returns a nonzero exit status and writes the error to stderr."
        },
        "retry_policy": "After write_outcome_unknown, use `ical list` to search for the event. After created_unverified, use `ical show --id ID --calendar CALENDAR`. Do not retry either write until confirming the event is absent. A not_created conflict-check timeout is safe to retry after Calendar responds."
    }

def build_guide() -> str:
    return """# ical Agent Guide

`ical` is an LLM-native CLI tool for macOS Calendar.app.

## Common Operations:
- List calendars: `ical calendars`
- List events in calendar: `ical list -c you@example.com --json`
- List events on a date: `ical list -c you@example.com --date 2026-10-27`
- List an inclusive date range: `ical list -c you@example.com --from 2026-10-27 --to 2026-10-31`
- Search event titles and locations: `ical search court -c you@example.com --limit 20`
- Search on a date: `ical search courthouse -c you@example.com --date 2026-10-27`
- Read any listed event by its Calendar ID: `ical show --id EVENT_ID --calendar you@example.com --json`
- Edit supplied fields by ID: `ical edit --id EVENT_ID --calendar you@example.com --title "New title"`
- Delete by ID only after explicit confirmation: `ical delete --id EVENT_ID --calendar you@example.com --yes`
- Upgrade the installed CLI: `ical update`
- Add and verify an event with conflict check & invites:
  `ical add -t "Meeting" -s "Monday, August 10, 2026 at 1:00 PM" -e "Monday, August 10, 2026 at 2:00 PM" -c "you@example.com" -a "user@example.com"`
- Get a machine-readable verified result:
  `ical add -t "Meeting" -s "Monday, August 10, 2026 at 1:00 PM" -e "Monday, August 10, 2026 at 2:00 PM" -c "you@example.com" -a "user@example.com" --json`
- Launch FastMCP stdio server for tool calling: `ical-mcp`
- Compatibility alias: `ical mcp`

`ical list` returns each event's Calendar ID, title, start/end, and location.
Use `ical search QUERY` to find matching titles or locations. Both commands
return IDs; use one with `ical show` to inspect an event created by any app. `show`
returns title, ISO 8601 start/end, calendar, location, description, URL, and
attendees. Missing optional text fields are empty strings. The MCP server offers
the same read path through `list_events`, `search_events`, and `show_event`.
`ical edit` checks the final time range before writing, changes only supplied
fields, then verifies the event by reading it back. `ical delete` requires
`--yes`, targets a Calendar ID, and reads Calendar back to confirm the event is
gone. If deletion cannot be verified, inspect Calendar before retrying.
`ical update` upgrades the installed CLI with `uv tool upgrade ical-mcp`; it
does not edit calendar data. MCP exposes matching `edit_calendar_event` and
`delete_calendar_event` tools; deletion requires `confirm=true`.

`ical add` only reports verified success after reading the created event back
by its Calendar ID. The JSON success object has `status: "verified"` and an
`event` with the same event details; each attendee has an `email` and RSVP `status`.
An `unknown` RSVP means no response has been recorded, not that the invite was
accepted.

Calendar automation calls have a 20-second timeout. If the conflict check times
out, `ical add` returns `not_created`; no event write was attempted, so retry
after Calendar responds. If the create write times out before
Calendar returns an event ID, JSON reports `status: "write_outcome_unknown"`
with an error. Search with `ical list` before retrying. If creation returns an
ID but read-back fails, the result is `created_unverified`; inspect it with
`ical show --id EVENT_ID --calendar CALENDAR`. **Do not retry either write
until confirming the event is absent**, to avoid a duplicate invite. `ical
show` is read-only and returns the same verified event envelope as `ical add`.
Calendar read failures are errors rather than empty event lists. See `ical
agent schema` for the machine-readable result and error contract.
"""

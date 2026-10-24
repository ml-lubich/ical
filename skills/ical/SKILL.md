---
license: MIT
name: ical
description: Read and write macOS Calendar.app events with the ical Typer CLI or its ical-mcp server. Use for listing calendars and events, scheduling meetings, inviting attendees, checking conflicts, and verifying event details or RSVP status.
---

# ical

Use the `ical` Typer CLI for Calendar.app and the standalone `ical-mcp` executable for MCP clients. The PyPI distribution is named `ical-mcp` and requires Python 3.10 or newer.

## Install

```sh
uv tool install --python 3.14 ical-mcp
```

Or with pip and Python 3.10 or newer:

```sh
pip install ical-mcp
```

From a source checkout:

```sh
uv tool install --editable .
```

The distribution installs the `ical` CLI and `ical-mcp` MCP server command. `ical mcp` remains a compatibility alias.

## CLI

```text
ical -h | --help
ical calendars
ical list --calendar CALENDAR [--json]
ical add --title TITLE --start START --end END [--calendar CALENDAR] [--attendee EMAIL ...]
ical show --id EVENT_ID [--calendar CALENDAR] [--json]
ical agent guide
ical agent schema
ical version
ical-mcp
```

`ical add` checks for conflicts by default, creates the event once, then reads it back by ID before reporting success. `ical show` is read-only and returns the same verified event data. Use `--json` on `add` or `show` for machine-readable output.

A verified JSON result has `status: "verified"` and an `event` with `id`, `title`, ISO 8601 `start` and `end`, `calendar`, and `attendees`. Each attendee includes `email` and RSVP `status`. `unknown` means Calendar has no recorded RSVP; it does not mean accepted.

## MCP

Configure an MCP client to launch `ical-mcp` over stdio. It exposes `list_calendars`, `list_events`, and `add_calendar_event`. Use `ical-mcp` in new configurations; `ical mcp` remains a compatibility alias.

## Timeouts and safe recovery

Calendar automation stops after 20 seconds and reports errors instead of waiting indefinitely. Do not blindly retry an event write after an uncertain result:

- `not_created`: the conflict check timed out before creation began. No event was written; retry after Calendar responds.
- `write_outcome_unknown`: creation timed out before an event ID came back. The event may exist; inspect `ical list` before retrying.
- `created_unverified`: Calendar returned an ID but read-back failed. Use `ical show --id EVENT_ID --calendar CALENDAR` to verify before retrying.
- `verification_failed`: `ical show` could not read the event. Retry the read after Calendar responds; do not repeat the create.

`ical list` reports Calendar automation failures instead of treating them as an empty calendar. `ical agent guide` documents the agent workflow; `ical agent schema` describes JSON results.

## macOS permission

The app running `ical` or `ical-mcp` needs macOS Automation permission to control Calendar.app. Grant it in System Settings → Privacy & Security → Automation. A harmless read such as `ical calendars` can trigger the permission prompt.

## Write safety

`calendars`, `list`, and `show` are read-only. `add` creates a real calendar event and sends invitations to the supplied attendees. Only run `add` when the user explicitly requests that event. Never loop or blindly retry an uncertain `add`, because that can create duplicate events and invitations.

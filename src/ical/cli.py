"""Command line interface for macOS Calendar.app."""

import json
import sys
import datetime
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from ical import __version__

EPILOG = """\
Examples:

  ical calendars
  ical list --calendar "you@example.com" --json
  ical add --title "Mock Interview" --start "Monday, Aug 10, 2026 at 1:00 PM" --end "Monday, Aug 10, 2026 at 2:00 PM" -a user@example.com
  ical-mcp

`ical mcp` remains a compatibility alias for `ical-mcp`.
Agents: run `ical agent guide` for a playbook, `ical agent schema` for JSON contract.
"""

app = typer.Typer(
    name="ical",
    help="macOS Calendar.app CLI and MCP server.",
    epilog=EPILOG,
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)
agent_app = typer.Typer(
    name="agent",
    help="Show the machine-readable schema and playbook.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)
app.add_typer(agent_app, name="agent")

console = Console()


def _event_json(event: dict) -> dict:
    """Return the stable, machine-readable fields shared by add and show."""
    return {
        key: value.isoformat() if isinstance(value, datetime.datetime) else value
        for key, value in event.items()
        if key in {"id", "title", "start", "end", "calendar", "attendees"}
    }


def _print_event(event: dict, label: str) -> None:
    start_text = event.get("start_str", str(event["start"]))
    end_text = event.get("end_str", str(event["end"]))
    console.print(
        f"[bold green]{label}.[/bold green] "
        f"{event['title']} — {start_text} to {end_text} ([cyan]{event['calendar']}[/cyan])"
    )
    attendees = event.get("attendees", [])
    if attendees:
        for guest in attendees:
            status = guest.get("status") or "status unavailable"
            console.print(f"  Invitee: {guest['email']} ({status})")
    else:
        console.print("  Invitees: none")
    console.print(f"  ID: {event['id']}")


@app.command("calendars")
def list_calendars() -> None:
    """List available calendars in Calendar.app."""
    from ical.calendar import run_applescript

    try:
        calendars = run_applescript(
            'tell application "Calendar" to get name of calendars'
        ).split(", ")
    except Exception as err:
        typer.echo(f"Error listing calendars: {err}", err=True)
        raise typer.Exit(code=1) from err

    table = Table(title="Calendars")
    table.add_column("Name", style="cyan")
    for calendar in calendars:
        table.add_row(calendar)
    console.print(table)


@app.command("add")
def add_event(
    title: Annotated[str, typer.Option("--title", "-t", help="Event title")],
    start: Annotated[str, typer.Option("--start", "-s", help="Start date and time")],
    end: Annotated[str, typer.Option("--end", "-e", help="End date and time")],
    calendar: Annotated[str, typer.Option("--calendar", "-c", help="Calendar name")] = "Calendar",
    attendee: Annotated[list[str] | None, typer.Option("--attendee", "-a", help="Attendee email; repeat for multiple attendees")] = None,
    description: Annotated[str, typer.Option("--description", "-d", help="Event description")] = "",
    location: Annotated[str, typer.Option("--location", "-l", help="Event location")] = "",
    check_conflict: Annotated[bool, typer.Option("--check-conflict/--no-check-conflict", help="Check for overlapping events")] = True,
    as_json: Annotated[bool, typer.Option("--json", "-j", help="Emit verified event as JSON")] = False,
) -> None:
    """Create an event, invite attendees, and verify it was saved."""
    from ical.calendar import CalendarTimeoutError, add_event as core_add_event, get_event_details

    try:
        result = core_add_event(
            title=title,
            start=start,
            end=end,
            calendar=calendar,
            attendee=attendee,
            description=description,
            location=location,
            check_conflict=check_conflict,
        )
    except CalendarTimeoutError as err:
        if err.write_may_have_succeeded:
            status = "write_outcome_unknown"
            details = {"status": status, "error": str(err)}
            message = (
                "Create request timed out; the write outcome is unknown. "
                "Do not retry yet. Check Calendar.app for the event first. "
                f"Details: {err}"
            )
        else:
            status = "not_created"
            details = {"status": status, "stage": "conflict_check", "error": str(err)}
            message = (
                "Calendar conflict check timed out. No event was created. "
                "You can retry after Calendar responds. "
                f"Details: {err}"
            )
        if as_json:
            typer.echo(json.dumps(details))
        else:
            typer.echo(message, err=True)
        raise typer.Exit(code=1) from err
    except (ValueError, RuntimeError) as err:
        typer.echo(f"Could not create event: {err}", err=True)
        raise typer.Exit(code=1) from err
    except Exception as err:
        typer.echo(f"Unexpected error creating event: {err}", err=True)
        raise typer.Exit(code=1) from err

    # The create call may have succeeded even if Calendar.app stops responding
    # during read-back. Never repeat the write automatically in that case.
    try:
        event = get_event_details(calendar, result["id"])
    except Exception as err:
        message = (
            f"Event was created, but verification failed (ID: {result['id']}). "
            f"Do not retry add; verify it with `ical show --id {result['id']} "
            f"--calendar {calendar}`. Details: {err}"
        )
        if as_json:
            typer.echo(json.dumps({"status": "created_unverified", "id": result["id"], "error": str(err)}))
        else:
            typer.echo(message, err=True)
        raise typer.Exit(code=1) from err

    if as_json:
        typer.echo(json.dumps({"status": "verified", "event": _event_json(event)}, ensure_ascii=False))
        return

    _print_event(event, "Event created and verified")


@app.command("show")
def show_event(
    event_id: Annotated[str, typer.Option("--id", help="Event ID returned by `ical add`")],
    calendar: Annotated[str, typer.Option("--calendar", "-c", help="Calendar name")] = "Calendar",
    as_json: Annotated[bool, typer.Option("--json", "-j", help="Emit verified event as JSON")] = False,
) -> None:
    """Read and verify one existing event by ID."""
    from ical.calendar import get_event_details

    try:
        event = get_event_details(calendar, event_id)
    except Exception as err:
        if as_json:
            typer.echo(json.dumps({"status": "verification_failed", "id": event_id, "error": str(err)}))
        else:
            typer.echo(f"Could not verify event {event_id!r}: {err}", err=True)
        raise typer.Exit(code=1) from err

    if as_json:
        typer.echo(json.dumps({"status": "verified", "event": _event_json(event)}, ensure_ascii=False))
        return
    _print_event(event, "Event verified")


@app.command("list")
def list_events(
    calendar: Annotated[str, typer.Option("--calendar", "-c", help="Calendar name")] = "Calendar",
    as_json: Annotated[bool, typer.Option("--json", "-j", help="Emit JSON output")] = False,
) -> None:
    """List events in a calendar."""
    from ical.calendar import get_events

    try:
        events = get_events(calendar)
        json_events = [
            {"title": event["title"], "start": event["start_str"], "end": event["end_str"]}
            for event in events
        ]
        if as_json:
            typer.echo(json.dumps({"calendar": calendar, "events": json_events}, ensure_ascii=False))
            return

        table = Table(title=f"Events in {calendar}")
        table.add_column("Title", style="bold white")
        table.add_column("Start", style="green")
        table.add_column("End", style="yellow")
        for event in events:
            table.add_row(event["title"], event["start_str"], event["end_str"])
        console.print(table)
    except Exception as err:
        typer.echo(f"Error listing events: {err}", err=True)
        raise typer.Exit(code=1) from err


@app.command("mcp")
def serve_mcp() -> None:
    """Run the FastMCP server over stdio."""
    from ical.mcp import run_server

    run_server()


@agent_app.command("schema")
def agent_schema_cmd() -> None:
    """Print the JSON command contract for agents."""
    from ical.agent import build_schema

    console.print_json(data=build_schema())


@agent_app.command("guide")
def agent_guide_cmd() -> None:
    """Print the Markdown agent playbook."""
    from ical.agent import build_guide

    sys.stdout.write(build_guide())


@app.command("version")
def version() -> None:
    """Print the installed version."""
    typer.echo(f"ical {__version__}")


if __name__ == "__main__":
    app()

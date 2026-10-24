"""Command line interface for macOS Calendar.app."""

import json
import sys
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
  ical mcp

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
) -> None:
    """Create a calendar event and invite attendees."""
    from ical.calendar import add_event as core_add_event

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
    except (ValueError, RuntimeError) as err:
        typer.echo(f"Could not create event: {err}", err=True)
        raise typer.Exit(code=1) from err
    except Exception as err:
        typer.echo(f"Unexpected error creating event: {err}", err=True)
        raise typer.Exit(code=1) from err

    console.print(f"[bold green]Event created.[/bold green] ID: {result['id']}")


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

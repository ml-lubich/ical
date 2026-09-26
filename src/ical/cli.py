import sys
import json
import typer
from rich.console import Console
from rich.table import Table
from typing import Optional, List
from ical.calendar import run_applescript, add_event as core_add_event, get_events as core_get_events
from ical.mcp import run_server
from ical import agent
from ical import __version__

EPILOG = """\
Examples:

  ical calendars
  ical list --calendar "michaelle.lubich@gmail.com" --json
  ical add --title "Mock Interview" --start "Monday, Aug 10, 2026 at 1:00 PM" --end "Monday, Aug 10, 2026 at 2:00 PM" -a user@example.com
  ical mcp

Agents: run `ical agent guide` for a playbook, `ical agent schema` for JSON contract.
"""

app = typer.Typer(
    name="ical",
    help="macOS Calendar.app CLI & MCP — agent-friendly calendar management.",
    epilog=EPILOG,
    no_args_is_help=True,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]}
)

agent_app = typer.Typer(
    name="agent",
    help="Machine-readable schema and playbook for LLM/automation use.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]}
)
app.add_typer(agent_app, name="agent")

console = Console()

@app.command("calendars")
def list_calendars():
    """List available calendars in Calendar.app."""
    script = 'tell application "Calendar" to get name of calendars'
    cals = run_applescript(script).split(", ")
    table = Table(title="Calendars")
    table.add_column("Name", style="cyan")
    for cal in cals:
        table.add_row(cal)
    console.print(table)

@app.command("add")
def add_event(
    title: str = typer.Option(..., "--title", "-t", help="Event title/summary"),
    start: str = typer.Option(..., "--start", "-s", help="Start time (e.g. 'Monday, August 10, 2026 at 1:00:00 PM')"),
    end: str = typer.Option(..., "--end", "-e", help="End time (e.g. 'Monday, August 10, 2026 at 2:00:00 PM')"),
    calendar: str = typer.Option("Calendar", "--calendar", "-c", help="Calendar name"),
    attendee: Optional[List[str]] = typer.Option(None, "--attendee", "-a", help="Attendee email address(es) to invite"),
    description: str = typer.Option("", "--description", "-d", help="Event description"),
    location: str = typer.Option("", "--location", "-l", help="Event location"),
    check_conflict: bool = typer.Option(True, "--check-conflict/--no-check-conflict", help="Enable/disable conflict detection")
):
    """Add a calendar event with conflict checking and attendee invites."""
    try:
        res = core_add_event(
            title=title,
            start=start,
            end=end,
            calendar=calendar,
            attendee=attendee,
            description=description,
            location=location,
            check_conflict=check_conflict
        )
        console.print(f"[bold green]✓ Event created![/bold green] ID: {res['id']}")
    except ValueError as err:
        console.print(f"[bold red]Conflict Warning:[/bold red] {err}")
        raise typer.Exit(code=1)
    except Exception as err:
        console.print(f"[bold red]Error creating event:[/bold red] {err}")
        raise typer.Exit(code=1)

@app.command("list")
def list_events(
    calendar: str = typer.Option("Calendar", "--calendar", "-c", help="Calendar name"),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON output")
):
    """List events in a specified calendar."""
    try:
        events = core_get_events(calendar)
        if as_json:
            console.print_json(data={"calendar": calendar, "events": events})
            return
        table = Table(title=f"Events in {calendar}")
        table.add_column("Title", style="bold white")
        table.add_column("Start", style="green")
        table.add_column("End", style="yellow")
        for evt in events:
            table.add_row(evt["title"], evt["start_str"], evt["end_str"])
        console.print(table)
    except Exception as err:
        console.print(f"[bold red]Error listing events:[/bold red] {err}")

@app.command("mcp")
def serve_mcp():
    """Run FastMCP server over stdio for AI agent integration."""
    run_server()

@agent_app.command("schema")
def agent_schema_cmd() -> None:
    """Print JSON command contract for LLM agents."""
    console.print_json(data=agent.build_schema())

@agent_app.command("guide")
def agent_guide_cmd() -> None:
    """Print markdown playbook for LLM agents."""
    sys.stdout.write(agent.build_guide())

@app.command("version")
def version():
    """Print ical version."""
    console.print(f"ical version {__version__} (LLM-Native Typer CLI + FastMCP)")

if __name__ == "__main__":
    app()

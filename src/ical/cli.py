import typer
from rich.console import Console
from rich.table import Table
from typing import Optional, List
from ical.calendar import run_applescript, add_event as core_add_event, get_events as core_get_events
from ical.mcp import run_server

app = typer.Typer(help="macOS Calendar.app CLI & MCP — agent-friendly calendar management.")
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
    calendar: str = typer.Option("Calendar", "--calendar", "-c", help="Calendar name")
):
    """List events in a specified calendar."""
    try:
        events = core_get_events(calendar)
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
    """Run MCP server over stdio for AI agent integration."""
    run_server()

@app.command("version")
def version():
    """Print ical version."""
    console.print("ical version 0.2.0 (CLI + MCP + Conflict Detection)")

if __name__ == "__main__":
    app()

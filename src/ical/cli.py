import subprocess
import json
import typer
from rich.console import Console
from rich.table import Table
from typing import Optional, List

app = typer.Typer(help="macOS Calendar.app CLI — agent-friendly calendar event management.")
console = Console()

def run_applescript(script: str) -> str:
    res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip())
    return res.stdout.strip()

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
    location: str = typer.Option("", "--location", "-l", help="Event location")
):
    """Add a calendar event and optionally invite attendees."""
    attendee_script = ""
    if attendee:
        for email in attendee:
            attendee_script += f'\n\t\t\tmake new attendee at end of attendees of newEvt with properties {{email:"{email}"}}'

    script = f'''
    tell application "Calendar"
        tell calendar "{calendar}"
            set newEvt to make new event with properties {{summary:"{title}", start date:date "{start}", end date:date "{end}", description:"{description}", location:"{location}"}}{attendee_script}
            return id of newEvt
        end tell
    end tell
    '''
    try:
        event_id = run_applescript(script)
        console.print(f"[bold green]✓ Event created![/bold green] ID: {event_id}")
    except Exception as err:
        console.print(f"[bold red]Error creating event:[/bold red] {err}")
        raise typer.Exit(code=1)

@app.command("list")
def list_events(
    calendar: str = typer.Option("Calendar", "--calendar", "-c", help="Calendar name")
):
    """List events in a specified calendar."""
    script = f'''
    tell application "Calendar"
        tell calendar "{calendar}"
            set res to ""
            set evts to every event
            repeat with e in evts
                set res to res & (summary of e) & " | " & (start date of e as string) & " | " & (end date of e as string) & "\n"
            end repeat
            return res
        end tell
    end tell
    '''
    try:
        output = run_applescript(script)
        table = Table(title=f"Events in {calendar}")
        table.add_column("Title", style="bold white")
        table.add_column("Start", style="green")
        table.add_column("End", style="yellow")
        for line in output.splitlines():
            if line.strip():
                parts = line.split(" | ")
                if len(parts) == 3:
                    table.add_row(parts[0], parts[1], parts[2])
        console.print(table)
    except Exception as err:
        console.print(f"[bold red]Error listing events:[/bold red] {err}")

@app.command("version")
def version():
    """Print ical version."""
    console.print("ical version 0.1.0")

if __name__ == "__main__":
    app()

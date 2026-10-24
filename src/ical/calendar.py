import subprocess
import datetime
from dateutil import parser
from typing import List, Dict, Any, Optional


APPLE_SCRIPT_TIMEOUT_SECONDS = 20


class CalendarAutomationError(RuntimeError):
    """Calendar.app automation returned an error."""


class CalendarTimeoutError(CalendarAutomationError):
    """Calendar.app did not respond within the bounded operation time."""

    def __init__(self, message: str, *, write_may_have_succeeded: bool = False):
        super().__init__(message)
        self.write_may_have_succeeded = write_may_have_succeeded


class EventNotFoundError(CalendarAutomationError):
    """No event with the requested ID exists in the selected calendar."""

def _escape_applescript(s: str) -> str:
    """Escape backslashes and double quotes so a value can be safely embedded
    inside a double-quoted AppleScript string literal."""
    return s.replace("\\", "\\\\").replace('"', '\\"')

def run_applescript(
    script: str,
    operation: str = "Calendar operation",
    *,
    write_may_have_succeeded: bool = False,
) -> str:
    try:
        res = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=APPLE_SCRIPT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as err:
        raise CalendarTimeoutError(
            f"{operation} timed out after {APPLE_SCRIPT_TIMEOUT_SECONDS}s. "
            "Calendar may still be processing; check the calendar before retrying.",
            write_may_have_succeeded=write_may_have_succeeded,
        ) from err
    if res.returncode != 0:
        detail = res.stderr.strip() or "Calendar.app returned an unspecified AppleScript error"
        raise CalendarAutomationError(f"{operation} failed: {detail}")
    return res.stdout.strip()

def parse_date(date_str: str) -> datetime.datetime:
    return parser.parse(date_str)

def get_events(calendar: str = "Calendar") -> List[Dict[str, Any]]:
    # Bulk-fetch each property across all events in one Apple Event call each
    # (summary of every event / start date of every event / ...) instead of
    # looping "repeat with e in evts" and querying properties per-event.
    # The per-event loop round-trips to Calendar.app 2-3x per event and is
    # catastrophically slow (multi-second-per-event, effectively hangs) on
    # any calendar with more than a handful of events - a well-known macOS
    # Calendar AppleScript scripting-bridge performance bug.
    script = f'''
    tell application "Calendar"
        tell calendar "{_escape_applescript(calendar)}"
            set summaries to summary of every event
            set starts to start date of every event
            set ends to end date of every event
        end tell
    end tell
    set res to ""
    repeat with i from 1 to (count of summaries)
        set res to res & (item i of summaries) & " | " & ((item i of starts) as string) & " | " & ((item i of ends) as string) & "\n"
    end repeat
    return res
    '''
    output = run_applescript(script, operation=f"Reading events from calendar {calendar!r}")
    events = []
    for line in output.splitlines():
        if line.strip():
            parts = line.split(" | ")
            if len(parts) == 3:
                try:
                    start_dt = parse_date(parts[1])
                    end_dt = parse_date(parts[2])
                    events.append({
                        "title": parts[0],
                        "start": start_dt,
                        "end": end_dt,
                        "start_str": parts[1],
                        "end_str": parts[2]
                    })
                except (ValueError, OverflowError):
                    continue
    return events


def get_event_details(calendar: str, event_id: str) -> Dict[str, Any]:
    """Read one event by ID, including invitee participation when available."""
    separator = "ASCII character 31"
    script = f'''
    tell application "Calendar"
        tell calendar "{_escape_applescript(calendar)}"
            set matchingEvents to every event whose id is "{_escape_applescript(event_id)}"
            if (count of matchingEvents) is 0 then return ""
            set targetEvent to item 1 of matchingEvents
            set fields to {{id of targetEvent as text, summary of targetEvent as text, ¬
                start date of targetEvent as text, end date of targetEvent as text}}
            set resultText to ""
            repeat with fieldValue in fields
                if resultText is not "" then set resultText to resultText & linefeed
                set resultText to resultText & (contents of fieldValue)
            end repeat
            repeat with guest in attendees of targetEvent
                set resultText to resultText & linefeed & (email of guest as text) & {separator} & ¬
                    (participation status of guest as text)
            end repeat
            return resultText
        end tell
    end tell
    '''
    output = run_applescript(script, operation=f"Verifying event {event_id!r}")
    lines = output.splitlines()
    if len(lines) < 4:
        raise EventNotFoundError(
            f"Event {event_id!r} was not found in calendar {calendar!r}."
        )
    try:
        start_dt = parse_date(lines[2])
        end_dt = parse_date(lines[3])
    except (ValueError, OverflowError) as err:
        raise CalendarAutomationError(
            f"Calendar returned invalid dates while verifying event {event_id!r}."
        ) from err
    attendees = []
    for line in lines[4:]:
        if chr(31) not in line:
            continue
        email, status = line.split(chr(31), 1)
        attendees.append({"email": email, "status": status})
    return {
        "id": lines[0],
        "title": lines[1],
        "start": start_dt,
        "end": end_dt,
        "start_str": lines[2],
        "end_str": lines[3],
        "calendar": calendar,
        "attendees": attendees,
    }

def check_conflicts(calendar: str, start_dt: datetime.datetime, end_dt: datetime.datetime) -> List[Dict[str, Any]]:
    existing = get_events(calendar)
    conflicts = []
    for evt in existing:
        # Check overlap: start1 < end2 and start2 < end1
        if evt["start"] < end_dt and start_dt < evt["end"]:
            conflicts.append(evt)
    return conflicts

def add_event(
    title: str,
    start: str,
    end: str,
    calendar: str = "Calendar",
    attendee: Optional[List[str]] = None,
    description: str = "",
    location: str = "",
    check_conflict: bool = True
) -> Dict[str, Any]:
    start_dt = parse_date(start)
    end_dt = parse_date(end)
    
    if check_conflict:
        conflicts = check_conflicts(calendar, start_dt, end_dt)
        if conflicts:
            conflict_titles = ", ".join([c["title"] for c in conflicts])
            raise ValueError(f"Conflict detected with existing event(s): {conflict_titles}")
            
    attendee_script = ""
    if attendee:
        for email in attendee:
            attendee_script += f'\n\t\t\tmake new attendee at end of attendees of newEvt with properties {{email:"{_escape_applescript(email)}"}}'

    script = f'''
    tell application "Calendar"
        tell calendar "{_escape_applescript(calendar)}"
            set newEvt to make new event with properties {{summary:"{_escape_applescript(title)}", start date:date "{start}", end date:date "{end}", description:"{_escape_applescript(description)}", location:"{_escape_applescript(location)}"}}{attendee_script}
            return id of newEvt
        end tell
    end tell
    '''
    event_id = run_applescript(
        script,
        operation=f"Creating event {title!r}",
        write_may_have_succeeded=True,
    )
    return {"id": event_id, "title": title, "start": start, "end": end, "calendar": calendar}

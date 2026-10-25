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
    value = parser.parse(date_str)
    if value.tzinfo is not None:
        value = value.astimezone().replace(tzinfo=None)
    return value


def _applescript_date_setup(name: str, value: datetime.datetime) -> str:
    """Set an AppleScript date using numeric components, avoiding locale parsing."""
    seconds = value.hour * 3600 + value.minute * 60 + value.second
    return (
        f"set {name} to current date\n"
        f"set day of {name} to 1\n"
        f"set year of {name} to {value.year}\n"
        f"set month of {name} to {value.month}\n"
        f"set day of {name} to {value.day}\n"
        f"set time of {name} to {seconds}\n"
    )


def date_window(start_value: str, end_value: str) -> tuple[datetime.datetime, datetime.datetime]:
    """Parse inclusive ISO date endpoints into a local half-open interval."""
    try:
        start_date = datetime.date.fromisoformat(start_value)
        end_date = datetime.date.fromisoformat(end_value)
    except ValueError as err:
        raise ValueError("Dates must use YYYY-MM-DD format") from err
    if start_date.isoformat() != start_value or end_date.isoformat() != end_value:
        raise ValueError("Dates must use YYYY-MM-DD format")
    if start_date > end_date:
        raise ValueError("Start date must be on or before end date")
    try:
        end_exclusive = end_date + datetime.timedelta(days=1)
    except OverflowError as err:
        raise ValueError("Date range end is outside the supported calendar range") from err
    return (
        datetime.datetime.combine(start_date, datetime.time.min),
        datetime.datetime.combine(end_exclusive, datetime.time.min),
    )

def get_events(
    calendar: str = "Calendar",
    *,
    start_before: Optional[datetime.datetime] = None,
    end_after: Optional[datetime.datetime] = None,
    query: Optional[str] = None,
) -> List[Dict[str, Any]]:
    # Bulk-fetch each property across all matching events in one Apple Event call each
    # (summary of every event / start date of every event / ...) instead of
    # looping "repeat with e in evts" and querying properties per-event.
    # The per-event loop round-trips to Calendar.app 2-3x per event and is
    # catastrophically slow (multi-second-per-event, effectively hangs) on
    # calendars with more than a handful of events - a well-known macOS
    # Calendar AppleScript scripting-bridge performance bug. Conflict checks
    # also constrain matchingEvents to the requested overlap window.
    if (start_before is None) != (end_after is None):
        raise ValueError("Both start_before and end_after are required for a bounded event query.")
    event_query = "every event"
    date_setup = ""
    text_query = ""
    if query is not None:
        escaped_query = _escape_applescript(query)
        text_query = f'(summary contains "{escaped_query}" or location contains "{escaped_query}")'
    if start_before is not None and end_after is not None:
        date_setup = (
            _applescript_date_setup("queryStart", end_after)
            + _applescript_date_setup("queryEnd", start_before)
        )
        event_query = (
            "every event whose start date is less than queryEnd "
            "and end date is greater than queryStart"
        )
    if text_query:
        if event_query == "every event":
            event_query = f"every event whose {text_query}"
        else:
            event_query = f"{event_query} and {text_query}"
    if start_before is not None:
        read_events = '''
        set res to ""
        set skippedEventCount to 0
        repeat with matchingEvent in matchingEvents
            try
                set eventId to id of matchingEvent as text
                set eventSummary to summary of matchingEvent as text
                set eventStart to start date of matchingEvent as text
                set eventEnd to end date of matchingEvent as text
                set eventLocation to location of matchingEvent
                if eventLocation is missing value then set eventLocation to ""
                set eventRecord to eventId & (ASCII character 31) & eventSummary & (ASCII character 31) & eventStart & (ASCII character 31) & eventEnd & (ASCII character 31) & (eventLocation as text)
                if res is not "" then set res to res & (ASCII character 30)
                set res to res & eventRecord
            on error errMsg number errNum
                set skippedEventCount to skippedEventCount + 1
            end try
        end repeat
        '''
    else:
        read_events = '''
        set res to ""
        set matchingCount to count of matchingEvents
        if matchingCount > 0 then
            try
                set eventIds to id of matchingEvents
                set eventTitles to summary of matchingEvents
                set eventStarts to start date of matchingEvents
                set eventEnds to end date of matchingEvents
                set eventLocations to location of matchingEvents
                set bulkReadSucceeded to true
            on error
                set bulkReadSucceeded to false
            end try
            if bulkReadSucceeded then
                repeat with i from 1 to matchingCount
                    set eventLocation to item i of eventLocations
                    if eventLocation is missing value then set eventLocation to ""
                    set eventRecord to (item i of eventIds as text) & (ASCII character 31) & (item i of eventTitles as text) & (ASCII character 31) & ((item i of eventStarts) as text) & (ASCII character 31) & ((item i of eventEnds) as text) & (ASCII character 31) & (eventLocation as text)
                    if res is not "" then set res to res & (ASCII character 30)
                    set res to res & eventRecord
                end repeat
            else
                set skippedEventCount to 0
                repeat with matchingEvent in matchingEvents
                    try
                        set eventId to id of matchingEvent as text
                        set eventSummary to summary of matchingEvent as text
                        set eventStart to start date of matchingEvent as text
                        set eventEnd to end date of matchingEvent as text
                        set eventLocation to location of matchingEvent
                        if eventLocation is missing value then set eventLocation to ""
                        set eventRecord to eventId & (ASCII character 31) & eventSummary & (ASCII character 31) & eventStart & (ASCII character 31) & eventEnd & (ASCII character 31) & (eventLocation as text)
                        if res is not "" then set res to res & (ASCII character 30)
                        set res to res & eventRecord
                    on error errMsg number errNum
                        set skippedEventCount to skippedEventCount + 1
                    end try
                end repeat
            end if
        end if
        '''

    script = f'''
    tell application "Calendar"
        tell calendar "{_escape_applescript(calendar)}"
            {date_setup}
            set matchingEvents to {event_query}
            {read_events}
        end tell
    end tell
    return res & "__ICAL_LIST_END__"
    '''
    output = run_applescript(script, operation=f"Reading events from calendar {calendar!r}")
    output = output.removesuffix("__ICAL_LIST_END__")
    events = []
    for record in output.split(chr(30)) if chr(30) in output else output.splitlines():
        parts = record.split(chr(31), 4)
        if len(parts) != 5:
            # Accept the old transport format for existing test doubles or callers.
            legacy = record.split(" | ")
            if len(legacy) != 3:
                continue
            event_id, title, start_text, end_text, location = "", legacy[0], legacy[1], legacy[2], ""
        else:
            event_id, title, start_text, end_text, location = parts
        try:
            start_dt = parse_date(start_text)
            end_dt = parse_date(end_text)
        except (ValueError, OverflowError):
            continue
        events.append({
            "id": event_id,
            "title": title,
            "start": start_dt,
            "end": end_dt,
            "start_str": start_text,
            "end_str": end_text,
            "location": location,
        })
    return events


def search_events(
    query: str,
    calendar: str = "Calendar",
    *,
    limit: int = 20,
    start_before: Optional[datetime.datetime] = None,
    end_after: Optional[datetime.datetime] = None,
) -> List[Dict[str, Any]]:
    """Find case-insensitive title/location substring matches in calendar order."""
    if not query.strip():
        raise ValueError("Search query cannot be empty")
    if limit < 1:
        raise ValueError("Search limit must be a positive integer")
    needle = query.casefold()
    if start_before is None and end_after is None:
        if query is not None:
            events = get_events(calendar, query=query)
        else:
            events = get_events(calendar)
    else:
        kwargs = {"start_before": start_before, "end_after": end_after}
        if query is not None:
            kwargs["query"] = query
        events = get_events(calendar, **kwargs)
    matches = []
    for event in events:
        if needle in event["title"].casefold() or needle in event.get("location", "").casefold():
            matches.append(event)
            if len(matches) == limit:
                break
    return matches


def get_event_details(calendar: str, event_id: str) -> Dict[str, Any]:
    """Read one event by ID, including invitee participation when available."""
    separator = "(ASCII character 31)"
    record_separator = "(ASCII character 30)"
    script = f'''
    tell application "Calendar"
        tell calendar "{_escape_applescript(calendar)}"
            set matchingEvents to every event whose id is "{_escape_applescript(event_id)}"
            if (count of matchingEvents) is 0 then return ""
            set targetEvent to item 1 of matchingEvents
            set eventLocation to location of targetEvent
            if eventLocation is missing value then set eventLocation to ""
            set eventDescription to description of targetEvent
            if eventDescription is missing value then set eventDescription to ""
            set eventURL to url of targetEvent
            if eventURL is missing value then set eventURL to ""
            set fields to {{id of targetEvent as text, summary of targetEvent as text, ¬
                start date of targetEvent as text, end date of targetEvent as text, ¬
                eventLocation as text, eventDescription as text, eventURL as text}}
            set resultText to ""
            repeat with fieldValue in fields
                if resultText is not "" then set resultText to resultText & {separator}
                set resultText to resultText & (contents of fieldValue)
            end repeat
            repeat with guest in attendees of targetEvent
                set resultText to resultText & {record_separator} & (email of guest as text) & {separator} & ¬
                    (participation status of guest as text)
            end repeat
            return resultText & "__ICAL_EVENT_END__"
        end tell
    end tell
    '''
    output = run_applescript(script, operation=f"Verifying event {event_id!r}")
    output = output.removesuffix("__ICAL_EVENT_END__")
    records = output.split(chr(30))
    fields = records[0].split(chr(31), 6) if records else []
    if len(fields) < 7:
        # Read-back compatibility for callers that mocked the old line format.
        legacy_lines = output.splitlines()
        if len(legacy_lines) >= 4:
            fields = legacy_lines[:4] + ["", "", ""]
            records = ["", *legacy_lines[4:]]
        else:
            fields = []
    if len(fields) < 7:
        raise EventNotFoundError(
            f"Event {event_id!r} was not found in calendar {calendar!r}."
        )
    try:
        start_dt = parse_date(fields[2])
        end_dt = parse_date(fields[3])
    except (ValueError, OverflowError) as err:
        raise CalendarAutomationError(
            f"Calendar returned invalid dates while verifying event {event_id!r}."
        ) from err
    attendees = []
    for line in records[1:]:
        if chr(31) not in line:
            continue
        email, status = line.split(chr(31), 1)
        attendees.append({"email": email, "status": status})
    return {
        "id": fields[0],
        "title": fields[1],
        "start": start_dt,
        "end": end_dt,
        "start_str": fields[2],
        "end_str": fields[3],
        "calendar": calendar,
        "location": fields[4],
        "description": fields[5],
        "url": fields[6],
        "attendees": attendees,
    }

def check_conflicts(calendar: str, start_dt: datetime.datetime, end_dt: datetime.datetime) -> List[Dict[str, Any]]:
    existing = get_events(calendar, start_before=end_dt, end_after=start_dt)
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

    date_setup = _applescript_date_setup("startDate", start_dt) + _applescript_date_setup("endDate", end_dt)
    script = f'''
    tell application "Calendar"
        tell calendar "{_escape_applescript(calendar)}"
            {date_setup}
            set newEvt to make new event with properties {{summary:"{_escape_applescript(title)}", start date:startDate, end date:endDate, description:"{_escape_applescript(description)}", location:"{_escape_applescript(location)}"}}{attendee_script}
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

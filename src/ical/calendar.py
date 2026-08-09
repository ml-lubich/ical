import subprocess
import datetime
from dateutil import parser
from typing import List, Dict, Any, Optional

def run_applescript(script: str) -> str:
    res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip())
    return res.stdout.strip()

def parse_date(date_str: str) -> datetime.datetime:
    return parser.parse(date_str)

def get_events(calendar: str = "Calendar") -> List[Dict[str, Any]]:
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
                    except Exception:
                        pass
        return events
    except Exception:
        return []

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
            attendee_script += f'\n\t\t\tmake new attendee at end of attendees of newEvt with properties {{email:"{email}"}}'

    script = f'''
    tell application "Calendar"
        tell calendar "{calendar}"
            set newEvt to make new event with properties {{summary:"{title}", start date:date "{start}", end date:date "{end}", description:"{description}", location:"{location}"}}{attendee_script}
            return id of newEvt
        end tell
    end tell
    '''
    event_id = run_applescript(script)
    return {"id": event_id, "title": title, "start": start, "end": end, "calendar": calendar}

import datetime
import subprocess
from unittest.mock import patch, MagicMock

import pytest

from ical.calendar import (
    run_applescript,
    _escape_applescript,
    parse_date,
    get_events,
    check_conflicts,
    add_event,
)


# ---- run_applescript (the true OS boundary) ----

def test_run_applescript_success():
    fake = MagicMock(returncode=0, stdout=" Home, Work \n", stderr="")
    with patch("ical.calendar.subprocess.run", return_value=fake) as mock_run:
        result = run_applescript('tell application "Calendar" to get name of calendars')
    assert result == "Home, Work"
    args, kwargs = mock_run.call_args
    assert args[0][0] == "osascript"
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True


def test_run_applescript_failure_raises():
    fake = MagicMock(returncode=1, stdout="", stderr=" execution error: boom ")
    with patch("ical.calendar.subprocess.run", return_value=fake):
        with pytest.raises(RuntimeError, match="execution error: boom"):
            run_applescript("bad script")


# ---- _escape_applescript ----

def test_escape_applescript_quotes_and_backslashes():
    assert _escape_applescript('Say "Hi" to Bob') == 'Say \\"Hi\\" to Bob'
    assert _escape_applescript("back\\slash") == "back\\\\slash"
    assert _escape_applescript("plain") == "plain"


# ---- parse_date ----

def test_parse_date_returns_datetime():
    dt = parse_date("Monday, August 10, 2026 at 1:00:00 PM")
    assert isinstance(dt, datetime.datetime)
    assert dt.year == 2026 and dt.month == 8 and dt.day == 10
    assert dt.hour == 13


def test_parse_date_invalid_raises():
    with pytest.raises(Exception):
        parse_date("not a date at all !!!")


# ---- get_events ----

def test_get_events_parses_lines():
    output = (
        "Therapy | Monday, August 10, 2026 at 6:30:00 PM | Monday, August 10, 2026 at 7:30:00 PM\n"
        "Standup | Tuesday, August 11, 2026 at 9:00:00 AM | Tuesday, August 11, 2026 at 9:15:00 AM\n"
    )
    with patch("ical.calendar.run_applescript", return_value=output):
        events = get_events("Work")
    assert len(events) == 2
    assert events[0]["title"] == "Therapy"
    assert events[0]["start"] == datetime.datetime(2026, 8, 10, 18, 30)
    assert events[0]["end"] == datetime.datetime(2026, 8, 10, 19, 30)
    assert events[1]["title"] == "Standup"


def test_get_events_skips_malformed_lines():
    # missing a " | " separator entirely -> fewer than 3 parts, skipped
    output = "Good | Monday, August 10, 2026 at 6:30:00 PM | Monday, August 10, 2026 at 7:30:00 PM\nmalformed line with no pipes\n\n"
    with patch("ical.calendar.run_applescript", return_value=output):
        events = get_events()
    assert len(events) == 1
    assert events[0]["title"] == "Good"


def test_get_events_skips_lines_with_unparseable_dates():
    output = "Bad | not-a-date | also-not-a-date\n"
    with patch("ical.calendar.run_applescript", return_value=output):
        events = get_events()
    assert events == []


def test_get_events_returns_empty_on_applescript_error():
    with patch("ical.calendar.run_applescript", side_effect=RuntimeError("Calendar not running")):
        events = get_events("Work")
    assert events == []


# ---- check_conflicts ----

def test_check_conflicts_detects_overlap():
    existing = [
        {
            "title": "Therapy",
            "start": datetime.datetime(2026, 8, 10, 18, 30),
            "end": datetime.datetime(2026, 8, 10, 19, 30),
        }
    ]
    with patch("ical.calendar.get_events", return_value=existing):
        conflicts = check_conflicts(
            "Work",
            datetime.datetime(2026, 8, 10, 19, 0),
            datetime.datetime(2026, 8, 10, 20, 0),
        )
    assert len(conflicts) == 1
    assert conflicts[0]["title"] == "Therapy"


def test_check_conflicts_no_overlap():
    existing = [
        {
            "title": "Therapy",
            "start": datetime.datetime(2026, 8, 10, 18, 30),
            "end": datetime.datetime(2026, 8, 10, 19, 30),
        }
    ]
    with patch("ical.calendar.get_events", return_value=existing):
        conflicts = check_conflicts(
            "Work",
            datetime.datetime(2026, 8, 10, 19, 45),
            datetime.datetime(2026, 8, 10, 20, 45),
        )
    assert conflicts == []


def test_check_conflicts_empty_calendar():
    with patch("ical.calendar.get_events", return_value=[]):
        conflicts = check_conflicts(
            "Work",
            datetime.datetime(2026, 8, 10, 19, 0),
            datetime.datetime(2026, 8, 10, 20, 0),
        )
    assert conflicts == []


# ---- add_event ----

def test_add_event_raises_on_conflict():
    conflicting = [{"title": "Therapy", "start": datetime.datetime(2026, 8, 10, 18, 30), "end": datetime.datetime(2026, 8, 10, 19, 30)}]
    with patch("ical.calendar.check_conflicts", return_value=conflicting):
        with pytest.raises(ValueError, match="Therapy"):
            add_event(
                title="Standup",
                start="Monday, August 10, 2026 at 6:45:00 PM",
                end="Monday, August 10, 2026 at 7:45:00 PM",
            )


def test_add_event_success_returns_id_and_metadata():
    with patch("ical.calendar.check_conflicts", return_value=[]), \
         patch("ical.calendar.run_applescript", return_value="event-id-123") as mock_run:
        result = add_event(
            title="Standup",
            start="Monday, August 10, 2026 at 9:00:00 AM",
            end="Monday, August 10, 2026 at 9:15:00 AM",
            calendar="Work",
            attendee=["alice@example.com", "bob@example.com"],
            description="Daily sync",
            location="Zoom",
        )
    assert result == {
        "id": "event-id-123",
        "title": "Standup",
        "start": "Monday, August 10, 2026 at 9:00:00 AM",
        "end": "Monday, August 10, 2026 at 9:15:00 AM",
        "calendar": "Work",
    }
    script = mock_run.call_args[0][0]
    assert 'email:"alice@example.com"' in script
    assert 'email:"bob@example.com"' in script
    assert 'tell calendar "Work"' in script


def test_add_event_no_check_conflict_skips_lookup():
    with patch("ical.calendar.check_conflicts") as mock_check, \
         patch("ical.calendar.run_applescript", return_value="event-id-456"):
        add_event(
            title="Standup",
            start="Monday, August 10, 2026 at 9:00:00 AM",
            end="Monday, August 10, 2026 at 9:15:00 AM",
            check_conflict=False,
        )
    mock_check.assert_not_called()


def test_add_event_escapes_quotes_in_script():
    with patch("ical.calendar.check_conflicts", return_value=[]), \
         patch("ical.calendar.run_applescript", return_value="event-id-789") as mock_run:
        add_event(
            title='Say "Hi"',
            start="Monday, August 10, 2026 at 9:00:00 AM",
            end="Monday, August 10, 2026 at 9:15:00 AM",
            description='Has "quotes" in it',
            location='The "Big" Room',
        )
    script = mock_run.call_args[0][0]
    assert 'summary:"Say \\"Hi\\""' in script
    assert 'description:"Has \\"quotes\\" in it"' in script
    assert 'location:"The \\"Big\\" Room"' in script


def test_add_event_no_attendees():
    with patch("ical.calendar.check_conflicts", return_value=[]), \
         patch("ical.calendar.run_applescript", return_value="event-id-000") as mock_run:
        add_event(
            title="Solo block",
            start="Monday, August 10, 2026 at 9:00:00 AM",
            end="Monday, August 10, 2026 at 9:15:00 AM",
        )
    script = mock_run.call_args[0][0]
    assert "make new attendee" not in script

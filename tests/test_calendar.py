import datetime
import subprocess
from unittest.mock import patch, MagicMock

import pytest

from ical.calendar import (
    run_applescript,
    _escape_applescript,
    parse_date,
    get_events,
    search_events,
    check_conflicts,
    add_event,
    CalendarTimeoutError,
    CalendarAutomationError,
    EventNotFoundError,
    get_event_details,
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
    assert kwargs["timeout"] > 0


def test_run_applescript_timeout_is_actionable():
    with patch("ical.calendar.subprocess.run", side_effect=subprocess.TimeoutExpired("osascript", 20)):
        with pytest.raises(CalendarTimeoutError, match="timed out") as exc:
            run_applescript("slow script", operation="reading events")
    assert exc.value.write_may_have_succeeded is False


def test_add_timeout_marks_write_outcome_unknown():
    with patch("ical.calendar.check_conflicts", return_value=[]), \
         patch("ical.calendar.subprocess.run", side_effect=subprocess.TimeoutExpired("osascript", 20)):
        with pytest.raises(CalendarTimeoutError) as exc:
            add_event(
                title="Standup",
                start="Monday, August 10, 2026 at 9:00:00 AM",
                end="Monday, August 10, 2026 at 9:15:00 AM",
            )
    assert exc.value.write_may_have_succeeded is True


def test_run_applescript_failure_raises():
    fake = MagicMock(returncode=1, stdout="", stderr=" execution error: boom ")
    with patch("ical.calendar.subprocess.run", return_value=fake):
        with pytest.raises(CalendarAutomationError, match="execution error: boom"):
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


def test_parse_date_normalizes_iso_offset_to_local_calendar_time():
    supplied = datetime.datetime.fromisoformat("2026-10-25T11:00:00-07:00")
    expected = supplied.astimezone().replace(tzinfo=None)
    assert parse_date("2026-10-25T11:00:00-07:00") == expected


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


def test_get_events_window_uses_strict_overlap_predicate():
    start = datetime.datetime(2026, 10, 25, 11, 0)
    end = datetime.datetime(2026, 10, 25, 13, 30)
    with patch("ical.calendar.run_applescript", return_value="") as mock_run:
        get_events("Work", start_before=end, end_after=start)
    script = mock_run.call_args.args[0]
    assert "set queryStart to current date" in script
    assert "set year of queryStart to 2026" in script
    assert "set month of queryStart to 10" in script
    assert "set day of queryStart to 25" in script
    assert "set time of queryStart to 39600" in script
    assert "set time of queryEnd to 48600" in script
    assert "every event whose start date is less than queryEnd" in script
    assert "and end date is greater than queryStart" in script


def test_get_events_window_requires_both_bounds():
    with pytest.raises(ValueError, match="Both"):
        get_events("Work", start_before=datetime.datetime(2026, 10, 25, 13, 30))


def test_get_events_bounded_query_uses_only_overlapping_events_and_escapes_calendar():
    start = datetime.datetime(2026, 10, 27, 0, 0)
    end = datetime.datetime(2026, 10, 28, 0, 0)
    with patch("ical.calendar.run_applescript", return_value="") as mock_run:
        get_events('Personal "Local"', start_before=end, end_after=start)

    script = mock_run.call_args.args[0]
    assert 'tell calendar "Personal \\"Local\\""' in script
    assert "set matchingEvents to every event whose start date is less than queryEnd" in script
    assert "and end date is greater than queryStart" in script
    assert "set day of queryStart to 27" in script
    assert "set day of queryEnd to 28" in script
    assert "repeat with matchingEvent in matchingEvents" in script
    assert "set eventSummary to summary of matchingEvent as text" in script
    assert "on error" in script
    assert "set summaries to summary of matchingEvents" not in script
    assert "set summaries to summary of every event" not in script


def test_get_events_search_query_uses_native_title_and_location_predicate():
    with patch("ical.calendar.run_applescript", return_value="") as mock_run:
        get_events('Work "Local"', query='court "case"')
    script = mock_run.call_args.args[0]
    assert 'summary contains "court \\"case\\""' in script
    assert 'location contains "court \\"case\\""' in script
    assert 'tell calendar "Work \\"Local\\""' in script


def test_get_events_include_identity_location_and_safe_record_delimiters():
    output = (
        "evt-1\x1fCourt | arraignment\ncontinued\x1f"
        "Tuesday, October 27, 2026 at 1:30:00 PM\x1f"
        "Tuesday, October 27, 2026 at 2:30:00 PM\x1f"
        "201 N. First Street | Room 2\x1e"
    )
    with patch("ical.calendar.run_applescript", return_value=output) as mock_run:
        events = get_events(
            "Personal",
            start_before=datetime.datetime(2026, 10, 28),
            end_after=datetime.datetime(2026, 10, 27),
        )

    assert len(events) == 1
    assert events[0]["id"] == "evt-1"
    assert events[0]["title"] == "Court | arraignment\ncontinued"
    assert events[0]["location"] == "201 N. First Street | Room 2"
    script = mock_run.call_args.args[0]
    assert "id of matchingEvent" in script
    assert "location of matchingEvent" in script
    assert "ASCII character 31" in script
    assert "ASCII character 30" in script


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


def test_get_events_propagates_applescript_error():
    with patch("ical.calendar.run_applescript", side_effect=RuntimeError("Calendar not running")):
        with pytest.raises(RuntimeError, match="Calendar not running"):
            get_events("Work")


def test_search_events_matches_title_or_location_case_insensitively_and_limits_results():
    events = [
        {"id": "1", "title": "Court appearance", "location": "San Jose", "start": 1},
        {"id": "2", "title": "Other", "location": "County COURTHOUSE", "start": 2},
        {"id": "3", "title": "Court follow-up", "location": "Remote", "start": 3},
        {"id": "4", "title": "Unrelated", "location": "Office", "start": 4},
    ]
    with patch("ical.calendar.get_events", return_value=events) as mock_get:
        results = search_events("court", "Work", limit=2)
    assert [event["id"] for event in results] == ["1", "2"]
    mock_get.assert_called_once_with("Work", query="court")


@pytest.mark.parametrize("query,limit", [(" ", 10), ("court", 0), ("court", -1)])
def test_search_events_rejects_blank_query_or_nonpositive_limit(query, limit):
    with pytest.raises(ValueError):
        search_events(query, limit=limit)


def test_get_event_details_returns_id_and_attendee_status():
    output = (
        "evt-1\x1fStandup\x1fMonday, August 10, 2026 at 9:00:00 AM"
        "\x1fMonday, August 10, 2026 at 9:15:00 AM\x1fRoom A"
        "\x1fDaily agenda\x1fhttps://example.test/event"
        "\x1ealice@example.com\x1faccepted"
    )
    with patch("ical.calendar.run_applescript", return_value=output) as mock_run:
        event = get_event_details("Work", "evt-1")
    assert event["id"] == "evt-1"
    assert event["title"] == "Standup"
    assert event["location"] == "Room A"
    assert event["description"] == "Daily agenda"
    assert event["url"] == "https://example.test/event"
    assert event["attendees"] == [{"email": "alice@example.com", "status": "accepted"}]
    assert 'tell calendar "Work"' in mock_run.call_args.args[0]
    script = mock_run.call_args.args[0]
    assert "location of targetEvent" in script
    assert "description of targetEvent" in script
    assert "url of targetEvent" in script


def test_get_event_details_missing_event_is_distinct():
    with patch("ical.calendar.run_applescript", return_value=""):
        with pytest.raises(EventNotFoundError, match="not found"):
            get_event_details("Work", "missing")


# ---- check_conflicts ----

def test_check_conflicts_detects_overlap():
    existing = [
        {
            "title": "Therapy",
            "start": datetime.datetime(2026, 8, 10, 18, 30),
            "end": datetime.datetime(2026, 8, 10, 19, 30),
        }
    ]
    with patch("ical.calendar.get_events", return_value=existing) as mock_get:
        conflicts = check_conflicts(
            "Work",
            datetime.datetime(2026, 8, 10, 19, 0),
            datetime.datetime(2026, 8, 10, 20, 0),
        )
    assert len(conflicts) == 1
    assert conflicts[0]["title"] == "Therapy"
    mock_get.assert_called_once_with(
        "Work",
        start_before=datetime.datetime(2026, 8, 10, 20, 0),
        end_after=datetime.datetime(2026, 8, 10, 19, 0),
    )


def test_check_conflicts_excludes_events_that_only_touch_window_edges():
    existing = [
        {"title": "Ends at start", "start": datetime.datetime(2026, 8, 10, 18, 0), "end": datetime.datetime(2026, 8, 10, 19, 0)},
        {"title": "Overlaps start", "start": datetime.datetime(2026, 8, 10, 18, 59), "end": datetime.datetime(2026, 8, 10, 19, 1)},
        {"title": "Overlaps end", "start": datetime.datetime(2026, 8, 10, 19, 59), "end": datetime.datetime(2026, 8, 10, 20, 1)},
        {"title": "Starts at end", "start": datetime.datetime(2026, 8, 10, 20, 0), "end": datetime.datetime(2026, 8, 10, 21, 0)},
    ]
    with patch("ical.calendar.get_events", return_value=existing):
        conflicts = check_conflicts(
            "Work",
            datetime.datetime(2026, 8, 10, 19, 0),
            datetime.datetime(2026, 8, 10, 20, 0),
        )
    assert [event["title"] for event in conflicts] == ["Overlaps start", "Overlaps end"]


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


def test_add_event_converts_iso_offset_into_exact_numeric_calendar_date():
    start = "2026-10-25T11:00:00-07:00"
    end = "2026-10-25T13:30:00-07:00"
    expected_start = datetime.datetime.fromisoformat(start).astimezone().replace(tzinfo=None)
    expected_end = datetime.datetime.fromisoformat(end).astimezone().replace(tzinfo=None)
    with patch("ical.calendar.check_conflicts", return_value=[]), \
         patch("ical.calendar.run_applescript", return_value="event-id-iso") as mock_run:
        result = add_event("Offset event", start, end)
    script = mock_run.call_args.args[0]
    assert f"set year of startDate to {expected_start.year}" in script
    assert f"set month of startDate to {expected_start.month}" in script
    assert f"set day of startDate to {expected_start.day}" in script
    assert f"set time of startDate to {expected_start.hour * 3600 + expected_start.minute * 60}" in script
    assert f"set year of endDate to {expected_end.year}" in script
    assert "start date:startDate, end date:endDate" in script
    assert 'date "2026-10-25T11:00:00-07:00"' not in script
    assert result["id"] == "event-id-iso"

    readback_start = expected_start.strftime("%A, %B %d, %Y at %I:%M:%S %p")
    readback_end = expected_end.strftime("%A, %B %d, %Y at %I:%M:%S %p")
    output = f"event-id-iso\nOffset event\n{readback_start}\n{readback_end}\n"
    with patch("ical.calendar.run_applescript", return_value=output):
        event = get_event_details("Calendar", result["id"])
    assert event["start"] == expected_start
    assert event["end"] == expected_end


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

import datetime
import tomllib
from pathlib import Path
from unittest.mock import patch

from ical.mcp import list_calendars, list_events, add_calendar_event, run_server


def test_list_calendars_tool():
    with patch("ical.mcp.run_applescript", return_value="Home, Work"):
        result = list_calendars()
    assert result == ["Home", "Work"]


def test_list_events_tool_shapes_output():
    events = [
        {"id": "event-1", "title": "Standup", "start": None, "end": None, "start_str": "Mon 9am", "end_str": "Mon 9:15am", "location": "Room 4"},
    ]
    with patch("ical.mcp.core_get_events", return_value=events) as mock_get:
        result = list_events(calendar="Work")
    mock_get.assert_called_once_with("Work")
    assert result == [{"id": "event-1", "title": "Standup", "start": "Mon 9am", "end": "Mon 9:15am", "location": "Room 4"}]


def test_list_events_tool_passes_single_date_as_bounded_local_window():
    with patch("ical.mcp.core_get_events", return_value=[]) as mock_get:
        result = list_events(calendar="Work", date="2026-10-27")
    assert result == []
    mock_get.assert_called_once_with(
        "Work",
        start_before=datetime.datetime(2026, 10, 28),
        end_after=datetime.datetime(2026, 10, 27),
    )


def test_list_events_tool_passes_inclusive_range_as_half_open_window():
    with patch("ical.mcp.core_get_events", return_value=[]) as mock_get:
        result = list_events(calendar="Work", from_date="2026-10-27", to_date="2026-10-29")
    assert result == []
    mock_get.assert_called_once_with(
        "Work",
        start_before=datetime.datetime(2026, 10, 30),
        end_after=datetime.datetime(2026, 10, 27),
    )


def test_list_events_tool_rejects_partial_and_conflicting_date_filters():
    import pytest

    with pytest.raises(ValueError, match="together"):
        list_events(calendar="Work", from_date="2026-10-27")
    with pytest.raises(ValueError, match="cannot be combined"):
        list_events(calendar="Work", date="2026-10-27", from_date="2026-10-27", to_date="2026-10-28")


def test_show_event_tool_reads_details_for_external_calendar_id():
    from ical import mcp as mcp_module

    show_event = getattr(mcp_module, "show_event")
    event = {
        "id": "external-event-id", "title": "Court appearance", "start_str": "Tue 1:30 PM",
        "end_str": "Tue 2:30 PM", "location": "Courthouse", "description": "Bring citation",
        "url": "https://example.test/court", "attendees": [],
    }
    with patch("ical.mcp.core_get_event_details", return_value=event) as mock_get:
        result = show_event(calendar="Personal", event_id="external-event-id")
    assert result == event
    mock_get.assert_called_once_with("Personal", "external-event-id")


def test_search_events_tool_delegates_query_date_and_limit():
    from ical import mcp as mcp_module

    search_tool = getattr(mcp_module, "search_events")
    with patch("ical.mcp.core_search_events", return_value=[], create=True) as mock_search:
        result = search_tool(
            query="court", calendar="Work", date="2026-10-27", limit=3,
        )
    assert result == []
    mock_search.assert_called_once_with(
        "court", "Work", limit=3,
        start_before=datetime.datetime(2026, 10, 28),
        end_after=datetime.datetime(2026, 10, 27),
    )


def test_add_calendar_event_tool_success():
    with patch("ical.mcp.core_add_event", return_value={"id": "abc", "title": "Standup"}) as mock_add:
        result = add_calendar_event(
            title="Standup",
            start="Mon 9am",
            end="Mon 9:15am",
            calendar="Work",
            attendees=["a@example.com"],
            description="d",
            location="l",
            check_conflict=True,
        )
    assert result == {"id": "abc", "title": "Standup"}
    mock_add.assert_called_once_with(
        title="Standup",
        start="Mon 9am",
        end="Mon 9:15am",
        calendar="Work",
        attendee=["a@example.com"],
        description="d",
        location="l",
        check_conflict=True,
    )


def test_add_calendar_event_tool_conflict_returns_error_payload():
    with patch("ical.mcp.core_add_event", side_effect=ValueError("Conflict detected with existing event(s): Therapy")):
        result = add_calendar_event(title="Standup", start="Mon 9am", end="Mon 9:15am")
    assert result["status"] == "conflict_detected"
    assert "Therapy" in result["error"]


def test_add_calendar_event_tool_generic_error_returns_failed_status():
    with patch("ical.mcp.core_add_event", side_effect=RuntimeError("Calendar app crashed")):
        result = add_calendar_event(title="Standup", start="Mon 9am", end="Mon 9:15am")
    assert result["status"] == "failed"
    assert "Calendar app crashed" in result["error"]


def test_run_server_invokes_stdio_transport():
    with patch("ical.mcp.mcp") as mock_mcp:
        run_server()
    mock_mcp.run.assert_called_once_with(transport="stdio")


def test_ical_mcp_entrypoint_targets_run_server():
    project = tomllib.loads(Path("pyproject.toml").read_text())
    assert project["project"]["scripts"]["ical-mcp"] == "ical.mcp:run_server"

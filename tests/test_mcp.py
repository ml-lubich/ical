from unittest.mock import patch

from ical.mcp import list_calendars, list_events, add_calendar_event, run_server


def test_list_calendars_tool():
    with patch("ical.mcp.run_applescript", return_value="Home, Work"):
        result = list_calendars()
    assert result == ["Home", "Work"]


def test_list_events_tool_shapes_output():
    events = [
        {"title": "Standup", "start": None, "end": None, "start_str": "Mon 9am", "end_str": "Mon 9:15am"},
    ]
    with patch("ical.mcp.core_get_events", return_value=events) as mock_get:
        result = list_events(calendar="Work")
    mock_get.assert_called_once_with("Work")
    assert result == [{"title": "Standup", "start": "Mon 9am", "end": "Mon 9:15am"}]


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

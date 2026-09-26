import json
from unittest.mock import patch

from typer.testing import CliRunner

from ical.cli import app
from ical import __version__

runner = CliRunner()


def test_calendars_command_lists_names():
    with patch("ical.cli.run_applescript", return_value="Home, Work"):
        result = runner.invoke(app, ["calendars"])
    assert result.exit_code == 0
    assert "Home" in result.stdout
    assert "Work" in result.stdout


def test_add_command_success():
    with patch(
        "ical.cli.core_add_event",
        return_value={"id": "evt-1", "title": "Standup", "start": "s", "end": "e", "calendar": "Work"},
    ) as mock_add:
        result = runner.invoke(
            app,
            [
                "add",
                "--title", "Standup",
                "--start", "Monday, August 10, 2026 at 9:00:00 AM",
                "--end", "Monday, August 10, 2026 at 9:15:00 AM",
                "--calendar", "Work",
                "--attendee", "a@example.com",
                "--attendee", "b@example.com",
            ],
        )
    assert result.exit_code == 0
    assert "Event created" in result.stdout
    assert "evt-1" in result.stdout
    kwargs = mock_add.call_args.kwargs
    assert kwargs["attendee"] == ["a@example.com", "b@example.com"]
    assert kwargs["check_conflict"] is True


def test_add_command_no_check_conflict_flag():
    with patch("ical.cli.core_add_event", return_value={"id": "evt-2", "title": "t", "start": "s", "end": "e", "calendar": "c"}) as mock_add:
        result = runner.invoke(
            app,
            [
                "add",
                "--title", "t",
                "--start", "s",
                "--end", "e",
                "--no-check-conflict",
            ],
        )
    assert result.exit_code == 0
    assert mock_add.call_args.kwargs["check_conflict"] is False


def test_add_command_conflict_exits_nonzero():
    with patch("ical.cli.core_add_event", side_effect=ValueError("Conflict detected with existing event(s): Therapy")):
        result = runner.invoke(app, ["add", "--title", "t", "--start", "s", "--end", "e"])
    assert result.exit_code == 1
    assert "Conflict Warning" in result.stdout
    assert "Therapy" in result.stdout


def test_add_command_generic_error_exits_nonzero():
    with patch("ical.cli.core_add_event", side_effect=RuntimeError("boom")):
        result = runner.invoke(app, ["add", "--title", "t", "--start", "s", "--end", "e"])
    assert result.exit_code == 1
    assert "Error creating event" in result.stdout


def test_list_command_json_output():
    events = [{"title": "Standup", "start": None, "end": None, "start_str": "Mon 9am", "end_str": "Mon 9:15am"}]
    with patch("ical.cli.core_get_events", return_value=events):
        result = runner.invoke(app, ["list", "--calendar", "Work", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["calendar"] == "Work"
    assert payload["events"][0]["title"] == "Standup"


def test_list_command_table_output():
    events = [{"title": "Standup", "start": None, "end": None, "start_str": "Mon 9am", "end_str": "Mon 9:15am"}]
    with patch("ical.cli.core_get_events", return_value=events):
        result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "Standup" in result.stdout
    assert "Mon 9am" in result.stdout


def test_list_command_handles_error():
    with patch("ical.cli.core_get_events", side_effect=RuntimeError("Calendar app crashed")):
        result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "Error listing events" in result.stdout


def test_mcp_command_runs_server():
    with patch("ical.cli.run_server") as mock_run_server:
        result = runner.invoke(app, ["mcp"])
    assert result.exit_code == 0
    mock_run_server.assert_called_once()


def test_agent_schema_command_prints_json():
    result = runner.invoke(app, ["agent", "schema"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["name"] == "ical"


def test_agent_guide_command_prints_markdown():
    result = runner.invoke(app, ["agent", "guide"])
    assert result.exit_code == 0
    assert "ical Agent Guide" in result.stdout


def test_version_command_matches_package_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_no_args_shows_help():
    # no_args_is_help=True still exits 2 (Click's standalone_mode UsageError convention)
    # while printing the help text.
    result = runner.invoke(app, [])
    assert result.exit_code == 2
    assert "ical" in result.stdout

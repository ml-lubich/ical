import datetime
import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from ical.cli import app
from ical import __version__
from ical.calendar import CalendarTimeoutError

runner = CliRunner()


def test_calendars_command_lists_names():
    with patch("ical.calendar.run_applescript", return_value="Home, Work"):
        result = runner.invoke(app, ["calendars"])
    assert result.exit_code == 0
    assert "Home" in result.stdout
    assert "Work" in result.stdout


def test_add_command_success():
    with patch(
        "ical.calendar.add_event",
        return_value={"id": "evt-1", "title": "Standup", "start": "s", "end": "e", "calendar": "Work"},
    ) as mock_add, patch(
        "ical.calendar.get_event_details",
        return_value={"id": "evt-1", "title": "Standup", "start": "Mon 9am", "end": "Mon 9:15am", "calendar": "Work", "attendees": [{"email": "a@example.com", "status": "unknown"}, {"email": "b@example.com", "status": "accepted"}]},
    ) as mock_get:
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
    assert "Event created and verified" in result.stdout
    assert "evt-1" in result.stdout
    assert "a@example.com" in result.stdout
    assert "unknown" in result.stdout
    mock_get.assert_called_once_with("Work", "evt-1")
    kwargs = mock_add.call_args.kwargs
    assert kwargs["attendee"] == ["a@example.com", "b@example.com"]
    assert kwargs["check_conflict"] is True


def test_add_command_no_check_conflict_flag():
    with patch("ical.calendar.add_event", return_value={"id": "evt-2", "title": "t", "start": "s", "end": "e", "calendar": "c"}) as mock_add, patch(
        "ical.calendar.get_event_details", return_value={"id": "evt-2", "title": "t", "start": "s", "end": "e", "calendar": "c", "attendees": []}
    ):
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
    with patch("ical.calendar.add_event", side_effect=ValueError("Conflict detected with existing event(s): Therapy")):
        result = runner.invoke(app, ["add", "--title", "t", "--start", "s", "--end", "e"])
    assert result.exit_code == 1
    assert "Could not create event" in result.stderr
    assert "Therapy" in result.stderr


def test_add_command_generic_error_exits_nonzero():
    with patch("ical.calendar.add_event", side_effect=RuntimeError("boom")):
        result = runner.invoke(app, ["add", "--title", "t", "--start", "s", "--end", "e"])
    assert result.exit_code == 1
    assert "Could not create event" in result.stderr


def test_add_readback_failure_keeps_id_and_does_not_retry():
    with patch("ical.calendar.add_event", return_value={"id": "evt-uncertain", "title": "t", "start": "s", "end": "e", "calendar": "c"}) as mock_add, patch(
        "ical.calendar.get_event_details", side_effect=TimeoutError("Calendar did not respond in time")
    ):
        result = runner.invoke(app, ["add", "-t", "t", "-s", "s", "-e", "e"])
    assert result.exit_code == 1
    assert "created, but verification failed" in result.stderr
    assert "evt-uncertain" in result.stderr
    mock_add.assert_called_once()


def test_add_json_has_stable_verified_payload():
    event = {"id": "evt-3", "title": "Planning", "start": "Mon 9am", "end": "Mon 10am", "calendar": "Work", "attendees": [{"email": "a@example.com", "status": "unknown"}]}
    with patch("ical.calendar.add_event", return_value=event), patch("ical.calendar.get_event_details", return_value=event):
        result = runner.invoke(app, ["add", "-t", "Planning", "-s", "s", "-e", "e", "-c", "Work", "-a", "a@example.com", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == {"status": "verified", "event": event}


def test_add_timeout_reports_unknown_write_outcome_without_retry():
    with patch("ical.calendar.add_event", side_effect=CalendarTimeoutError("Creating event timed out", write_may_have_succeeded=True)) as mock_add:
        result = runner.invoke(app, ["add", "-t", "t", "-s", "s", "-e", "e", "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload == {"status": "write_outcome_unknown", "error": "Creating event timed out"}
    mock_add.assert_called_once()


def test_add_timeout_human_output_warns_not_to_retry():
    with patch("ical.calendar.add_event", side_effect=CalendarTimeoutError("Creating event timed out", write_may_have_succeeded=True)):
        result = runner.invoke(app, ["add", "-t", "t", "-s", "s", "-e", "e"])
    assert result.exit_code == 1
    assert "outcome is unknown" in result.stderr
    assert "Do not retry" in result.stderr


def test_add_precheck_timeout_reports_no_event_created_json():
    with patch("ical.calendar.add_event", side_effect=CalendarTimeoutError("Reading conflict window timed out")) as mock_add:
        result = runner.invoke(app, ["add", "-t", "t", "-s", "s", "-e", "e", "--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout) == {
        "status": "not_created",
        "stage": "conflict_check",
        "error": "Reading conflict window timed out",
    }
    mock_add.assert_called_once()


def test_add_precheck_timeout_human_says_no_event_was_created():
    with patch("ical.calendar.add_event", side_effect=CalendarTimeoutError("Reading conflict window timed out")):
        result = runner.invoke(app, ["add", "-t", "t", "-s", "s", "-e", "e"])
    assert result.exit_code == 1
    assert "conflict check timed out" in result.stderr
    assert "No event was created" in result.stderr
    assert "retry after Calendar responds" in result.stderr


def test_show_event_json_output_is_read_only_and_complete():
    event = {
        "id": "evt-joe", "title": "Work session with Joe", "start": datetime.datetime(2026, 10, 24, 11),
        "end": datetime.datetime(2026, 10, 24, 14), "start_str": "Sat 11am", "end_str": "Sat 2pm",
        "calendar": "Personal", "location": "Room 4", "description": "Bring the documents",
        "url": "https://example.test/event", "attendees": [{"email": "jheupler@berkeley.edu", "status": "unknown"}],
    }
    with patch("ical.calendar.get_event_details", return_value=event) as mock_show, patch("ical.calendar.add_event") as mock_add:
        result = runner.invoke(app, ["show", "--id", "evt-joe", "--calendar", "Personal", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == {
        "status": "verified",
        "event": {
            "id": "evt-joe", "title": "Work session with Joe", "start": "2026-10-24T11:00:00",
            "end": "2026-10-24T14:00:00", "calendar": "Personal",
            "location": "Room 4", "description": "Bring the documents", "url": "https://example.test/event",
            "attendees": [{"email": "jheupler@berkeley.edu", "status": "unknown"}],
        },
    }
    mock_show.assert_called_once_with("Personal", "evt-joe")
    mock_add.assert_not_called()


def test_show_event_human_output_includes_attendee_status():
    event = {"id": "evt-joe", "title": "Work session with Joe", "start": "s", "end": "e", "start_str": "Sat 11am", "end_str": "Sat 2pm", "calendar": "Personal", "location": "Room 4", "description": "Bring documents", "url": "https://example.test/event", "attendees": [{"email": "jheupler@berkeley.edu", "status": "unknown"}]}
    with patch("ical.calendar.get_event_details", return_value=event):
        result = runner.invoke(app, ["show", "--id", "evt-joe", "--calendar", "Personal"])
    assert result.exit_code == 0
    assert "Work session with Joe" in result.stdout
    assert "jheupler@berkeley.edu" in result.stdout
    assert "unknown" in result.stdout
    assert "Room 4" in result.stdout
    assert "Bring documents" in result.stdout
    assert "https://example.test/event" in result.stdout


def test_list_command_json_output():
    events = [{"title": "Standup", "start": None, "end": None, "start_str": "Mon 9am", "end_str": "Mon 9:15am"}]
    with patch("ical.calendar.get_events", return_value=events):
        result = runner.invoke(app, ["list", "--calendar", "Work", "-j"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["calendar"] == "Work"
    assert payload["events"][0]["title"] == "Standup"


def test_list_command_json_output_with_real_datetimes():
    # Regression test: core_get_events() returns real datetime objects in
    # "start"/"end" (see ical.calendar.get_events); the JSON path must not
    # pass those straight to console.print_json, which raises
    # "Object of type datetime is not JSON serializable" and gets
    # swallowed by the command's own error handler (exit 0, broken output).
    events = [
        {
            "id": "standup-event-id",
            "title": "Standup",
            "start": datetime.datetime(2026, 8, 10, 9, 0),
            "end": datetime.datetime(2026, 8, 10, 9, 15),
            "start_str": "Mon 9am",
            "end_str": "Mon 9:15am",
            "location": "Room 4",
        }
    ]
    with patch("ical.calendar.get_events", return_value=events):
        result = runner.invoke(app, ["list", "--calendar", "Work", "--json"])
    assert result.exit_code == 0
    assert "Error listing events" not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["events"][0] == {
        "id": "standup-event-id", "title": "Standup", "start": "Mon 9am", "end": "Mon 9:15am", "location": "Room 4",
    }


def test_list_command_table_output():
    events = [{"id": "standup-event-id", "title": "Standup", "start": None, "end": None, "start_str": "Mon 9am", "end_str": "Mon 9:15am", "location": "Room 4"}]
    with patch("ical.calendar.get_events", return_value=events):
        result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "Standup" in result.stdout
    assert "Mon 9am" in result.stdout
    assert "standup-event-id" in result.stdout
    assert "Room 4" in result.stdout


def test_list_command_handles_error():
    with patch("ical.calendar.get_events", side_effect=RuntimeError("Calendar app crashed")):
        result = runner.invoke(app, ["list"])
    assert result.exit_code == 1
    assert "Error listing events" in result.stderr


def test_list_single_date_passes_local_day_window_and_keeps_json_shape():
    events = [{
        "id": "court-event-id",
        "title": "Court appearance",
        "start": datetime.datetime(2026, 10, 27, 13, 30),
        "end": datetime.datetime(2026, 10, 27, 14, 30),
        "start_str": "Tue Oct 27 1:30 PM",
        "end_str": "Tue Oct 27 2:30 PM",
        "location": "201 N. First Street, San Jose, CA",
    }]
    with patch("ical.calendar.get_events", return_value=events) as mock_get:
        result = runner.invoke(app, ["list", "-c", "Personal", "--date", "2026-10-27", "--json"])

    assert result.exit_code == 0
    mock_get.assert_called_once_with(
        "Personal",
        start_before=datetime.datetime(2026, 10, 28),
        end_after=datetime.datetime(2026, 10, 27),
    )
    payload = json.loads(result.stdout)
    assert payload == {
        "calendar": "Personal",
        "events": [{
            "id": "court-event-id", "title": "Court appearance", "start": "Tue Oct 27 1:30 PM",
            "end": "Tue Oct 27 2:30 PM", "location": "201 N. First Street, San Jose, CA",
        }],
    }


def test_list_human_output_includes_event_id_and_location():
    event = {
        "id": "court-event-id", "title": "Court appearance", "start": None, "end": None,
        "start_str": "Tue Oct 27 1:30 PM", "end_str": "Tue Oct 27 2:30 PM",
        "location": "201 N. First Street, San Jose, CA",
    }
    with patch("ical.calendar.get_events", return_value=[event]):
        result = runner.invoke(app, ["list", "--date", "2026-10-27"])
    assert result.exit_code == 0
    assert "court-event-id" in result.stdout
    assert "201 N. First Street, San Jose, CA" in result.stdout


def test_list_inclusive_date_range_passes_half_open_window():
    with patch("ical.calendar.get_events", return_value=[]) as mock_get:
        result = runner.invoke(app, [
            "list", "--from", "2026-10-27", "--to", "2026-10-29", "--json",
        ])

    assert result.exit_code == 0
    mock_get.assert_called_once_with(
        "Calendar",
        start_before=datetime.datetime(2026, 10, 30),
        end_after=datetime.datetime(2026, 10, 27),
    )
    assert json.loads(result.stdout) == {"calendar": "Calendar", "events": []}


@pytest.mark.parametrize("args", [
    ["--date", "2026-02-30"],
    ["--date", "Oct 27, 2026"],
    ["--from", "2026-10-27"],
    ["--to", "2026-10-29"],
    ["--from", "2026-10-29", "--to", "2026-10-27"],
    ["--date", "2026-10-27", "--from", "2026-10-27", "--to", "2026-10-29"],
])
def test_list_rejects_invalid_or_ambiguous_date_filters_without_calendar_call(args):
    with patch("ical.calendar.get_events") as mock_get:
        result = runner.invoke(app, ["list", *args])

    assert result.exit_code != 0
    assert "Error listing events" in result.stderr
    mock_get.assert_not_called()


def test_list_help_documents_single_day_and_range_filters():
    result = runner.invoke(app, ["list", "-h"])
    assert result.exit_code == 0
    for option in ("--date", "--from", "--to", "--calendar", "--json"):
        assert option in result.output


def test_search_command_passes_filters_and_limit_and_keeps_event_identity():
    events = [{
        "id": "court-event-id", "title": "Court Appearance", "location": "San Jose Courthouse",
        "start": datetime.datetime(2026, 10, 27, 13, 30), "end": datetime.datetime(2026, 10, 27, 14, 30),
        "start_str": "Tue Oct 27 1:30 PM", "end_str": "Tue Oct 27 2:30 PM",
    }]
    with patch("ical.calendar.search_events", return_value=events) as mock_search:
        result = runner.invoke(app, [
            "search", "court", "-c", "Personal", "--date", "2026-10-27", "--limit", "5", "--json",
        ])
    assert result.exit_code == 0
    mock_search.assert_called_once_with(
        "court", "Personal", limit=5,
        start_before=datetime.datetime(2026, 10, 28),
        end_after=datetime.datetime(2026, 10, 27),
    )
    assert json.loads(result.stdout) == {
        "calendar": "Personal",
        "events": [{
            "id": "court-event-id", "title": "Court Appearance", "start": "Tue Oct 27 1:30 PM",
            "end": "Tue Oct 27 2:30 PM", "location": "San Jose Courthouse",
        }],
    }


def test_search_command_requires_query_and_help_documents_filters():
    missing = runner.invoke(app, ["search"])
    assert missing.exit_code == 2
    help_result = runner.invoke(app, ["search", "-h"])
    assert help_result.exit_code == 0
    for option in ("--calendar", "--date", "--from", "--to", "--limit", "--json"):
        assert option in help_result.output


def test_search_agent_contract_and_guide_document_query():
    from ical.agent import build_schema, build_guide

    assert "search" in build_schema()["commands"]
    assert "search_events" in build_schema()["mcp_tools"]
    assert "ical search QUERY" in build_guide()


def test_agent_schema_and_guide_document_event_discovery_details_and_date_filters():
    from ical.agent import build_schema, build_guide

    schema = build_schema()
    guide = build_guide()
    schema_text = json.dumps(schema)
    assert "--date" in schema_text
    assert "--from" in schema_text
    assert "--to" in schema_text
    assert '"id"' in schema_text
    assert '"location"' in schema_text
    assert "--date" in guide
    assert "location" in guide.lower()


def test_mcp_command_runs_server():
    with patch("ical.mcp.run_server") as mock_run_server:
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


def test_root_version_flags_match_package_version():
    for flag in ("-V", "--version"):
        result = runner.invoke(app, [flag])
        assert result.exit_code == 0
        assert __version__ in result.stdout


def test_no_args_shows_help():
    # no_args_is_help=True still exits 2 (Click's standalone_mode UsageError convention)
    # while printing the help text.
    result = runner.invoke(app, [])
    assert result.exit_code == 2
    assert "ical" in result.stdout


def test_help_contract_at_root_and_agent_group():
    for args in (["-h"], ["--help"], ["agent", "-h"], ["agent", "--help"]):
        result = runner.invoke(app, args)
        assert result.exit_code == 0, result.output
        assert "--install-completion" not in result.output
        assert "--show-completion" not in result.output


def test_edit_event_delegates_only_supplied_fields():
    details = {"id": "evt-1", "title": "New title", "start": "start", "end": "end", "calendar": "Work", "attendees": []}
    with patch("ical.calendar.edit_event", return_value={"id": "evt-1", "calendar": "Work"}) as mock_edit, patch(
        "ical.calendar.get_event_details", return_value=details,
    ) as mock_get:
        result = runner.invoke(app, ["edit", "--id", "evt-1", "--calendar", "Work", "--title", "New title"])
    assert result.exit_code == 0
    mock_edit.assert_called_once_with(
        "Work", "evt-1", title="New title", start=None, end=None,
        location=None, description=None,
    )
    mock_get.assert_called_once_with("Work", "evt-1")


def test_edit_event_requires_at_least_one_field():
    with patch("ical.calendar.edit_event") as mock_edit:
        result = runner.invoke(app, ["edit", "--id", "evt-1"])
    assert result.exit_code == 1
    assert "at least one" in result.stderr.lower()
    mock_edit.assert_not_called()


def test_delete_event_requires_explicit_yes_and_delegates():
    with patch("ical.calendar.delete_event", return_value={"id": "evt-1", "calendar": "Work"}) as mock_delete:
        declined = runner.invoke(app, ["delete", "--id", "evt-1", "--calendar", "Work"])
        assert declined.exit_code != 0
        mock_delete.assert_not_called()
        confirmed = runner.invoke(app, ["delete", "--id", "evt-1", "--calendar", "Work", "--yes"])
    assert confirmed.exit_code == 0
    assert "evt-1" in confirmed.stdout
    mock_delete.assert_called_once_with("Work", "evt-1")


def test_delete_event_failure_warns_before_retry():
    with patch("ical.calendar.delete_event", side_effect=RuntimeError("verification failed")):
        result = runner.invoke(app, ["delete", "--id", "evt-1", "--calendar", "Work", "--yes"])
    assert result.exit_code == 1
    assert "inspect Calendar before retrying" in result.stderr


def test_delete_event_json_failure_reports_unknown_outcome():
    import json

    with patch("ical.calendar.delete_event", side_effect=RuntimeError("verification failed")):
        result = runner.invoke(app, ["delete", "--id", "evt-1", "--calendar", "Work", "--yes", "--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["status"] == "delete_outcome_unknown"


def test_update_command_runs_uv_tool_upgrade_and_surfaces_output():
    import subprocess

    with patch("ical.cli.subprocess.run", return_value=subprocess.CompletedProcess(
        args=["uv", "tool", "upgrade", "ical-mcp"], returncode=0, stdout="", stderr="Installed ical-mcp",
    )) as mock_run:
        result = runner.invoke(app, ["update"])
    assert result.exit_code == 0
    assert "Installed ical-mcp" in result.stdout
    mock_run.assert_called_once_with(
        ["uv", "tool", "upgrade", "ical-mcp"], capture_output=True, check=False, text=True,
    )


def test_update_command_reports_completion_when_uv_is_quiet():
    import subprocess

    with patch("ical.cli.subprocess.run", return_value=subprocess.CompletedProcess(
        args=["uv", "tool", "upgrade", "ical-mcp"], returncode=0, stdout="", stderr="",
    )):
        result = runner.invoke(app, ["update"])
    assert result.exit_code == 0
    assert "upgrade completed" in result.stdout.lower()


def test_update_command_returns_nonzero_on_upgrade_failure():
    import subprocess

    with patch("ical.cli.subprocess.run", return_value=subprocess.CompletedProcess(
        args=["uv", "tool", "upgrade", "ical-mcp"], returncode=2, stdout="", stderr="package not installed",
    )):
        result = runner.invoke(app, ["update"])
    assert result.exit_code == 1
    assert "package not installed" in result.stderr


def test_new_commands_have_nested_help():
    for command in ("update", "edit", "delete"):
        result = runner.invoke(app, [command, "-h"])
        assert result.exit_code == 0

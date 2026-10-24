from ical.agent import build_schema, build_guide


def test_build_schema_structure():
    schema = build_schema()
    assert schema["name"] == "ical"
    assert set(schema["commands"].keys()) == {"calendars", "list", "show", "add", "mcp"}
    assert "--title" in schema["commands"]["add"]["flags"]
    assert "--calendar" in schema["commands"]["list"]["flags"]
    assert "--json" in schema["commands"]["add"]["flags"]
    assert set(schema["commands"]["show"]["flags"]) == {"--id", "--calendar", "--json"}


def test_agent_contract_explains_verification_and_safe_retry():
    schema = build_schema()
    guide = build_guide()
    assert "timeout" in schema["errors"]
    assert "write_outcome_unknown" in schema["errors"]
    assert "not_created" in schema["errors"]
    assert "Do not retry" in guide
    assert "RSVP `status`" in guide
    assert "attendees" in schema["add_result"]["event"]
    assert schema["add_result"]["status"] == ["verified", "created_unverified", "write_outcome_unknown", "not_created"]
    assert "write_outcome_unknown" in guide
    assert "ical show --id" in guide
    assert schema["add_result"]["show_result"]["failure"]["status"] == "verification_failed"


def test_build_guide_mentions_commands():
    guide = build_guide()
    assert isinstance(guide, str)
    assert "ical calendars" in guide
    assert "ical add" in guide
    assert "ical-mcp" in guide
    assert "ical mcp" in guide

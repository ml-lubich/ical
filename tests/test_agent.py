from ical.agent import build_schema, build_guide


def test_build_schema_structure():
    schema = build_schema()
    assert schema["name"] == "ical"
    assert set(schema["commands"].keys()) == {"calendars", "list", "add", "mcp"}
    assert "--title" in schema["commands"]["add"]["flags"]
    assert "--calendar" in schema["commands"]["list"]["flags"]


def test_build_guide_mentions_commands():
    guide = build_guide()
    assert isinstance(guide, str)
    assert "ical calendars" in guide
    assert "ical add" in guide
    assert "ical mcp" in guide

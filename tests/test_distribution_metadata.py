import importlib.util
from pathlib import Path

try:
    import tomllib
except ImportError:  # Python 3.10 uses the project dependency.
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_distribution_name_and_executables_are_standardized():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]

    assert project["name"] == "ical-mcp"
    assert project["scripts"] == {
        "ical": "ical.cli:app",
        "ical-mcp": "ical.mcp:run_server",
    }
    assert project["requires-python"] == ">=3.10"
    assert project["license"] == "MIT"
    assert project["license-files"] == ["LICENSE"]
    assert not any("email" in author for author in project.get("authors", []))
    assert importlib.util.find_spec("ical") is not None


def test_readme_uses_distribution_name_for_installation():
    readme = (ROOT / "README.md").read_text()

    assert "uv tool install --python 3.14 ical-mcp" in readme
    assert "pip install ical-mcp" in readme
    assert "uv tool install --editable ." in readme
    assert "mac-ical" not in readme
    assert "delete calendar events" not in readme

    skill = (ROOT / "skills" / "ical" / "SKILL.md").read_text()
    assert "uv tool install --python 3.14 ical-mcp" in skill
    assert "ical show --id" in skill
    assert "ical-mcp" in skill
    assert "write_outcome_unknown" in skill
    assert "created_unverified" in skill
    assert "mac-ical" not in skill

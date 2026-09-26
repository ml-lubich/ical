# ical CLI

macOS Calendar.app CLI tool — schedule, invite, list, delete calendar events.

## Install
```bash
pip install mac-ical
# or
brew install ml-lubich/tap/ical
```

From a checkout:

```bash
uv tool install -e ~/dev/ical
```

## Usage
```bash
ical calendars
ical add --title "Mock Interview - Final Round EchoStar #1" --start "Monday, August 10, 2026 at 1:00:00 PM" --end "Monday, August 10, 2026 at 2:00:00 PM" -a walkingon2008@aol.com -c michaelle.lubich@gmail.com
ical list -c michaelle.lubich@gmail.com
```

## Testing
```bash
uv run --extra dev pytest --cov=ical --cov-report=term-missing
```
Tests mock only the OS boundary (`subprocess`/`osascript`); parsing, conflict detection, CLI dispatch, and MCP tool functions run for real.

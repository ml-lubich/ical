# ical CLI

macOS Calendar.app CLI tool — schedule, invite, list, delete calendar events.

## Install
```bash
uv tool install -e ~/dev/ical
```

## Usage
```bash
ical calendars
ical add --title "Mock Interview - Final Round EchoStar #1" --start "Monday, August 10, 2026 at 1:00:00 PM" --end "Monday, August 10, 2026 at 2:00:00 PM" -a walkingon2008@aol.com -c michaelle.lubich@gmail.com
ical list -c michaelle.lubich@gmail.com
```

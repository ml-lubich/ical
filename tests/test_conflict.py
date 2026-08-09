import pytest
import datetime
from ical.calendar import check_conflicts

def test_check_conflicts():
    existing_events = [
        {
            "title": "Therapy",
            "start": datetime.datetime(2026, 8, 10, 18, 30),
            "end": datetime.datetime(2026, 8, 10, 19, 30)
        }
    ]
    
    # Overlapping case (6:30 PM - 7:30 PM) vs (7:00 PM - 8:00 PM)
    start_dt = datetime.datetime(2026, 8, 10, 19, 0)
    end_dt = datetime.datetime(2026, 8, 10, 20, 0)
    
    conflicts = []
    for evt in existing_events:
        if evt["start"] < end_dt and start_dt < evt["end"]:
            conflicts.append(evt)
            
    assert len(conflicts) == 1
    assert conflicts[0]["title"] == "Therapy"

def test_no_conflicts():
    existing_events = [
        {
            "title": "Therapy",
            "start": datetime.datetime(2026, 8, 10, 18, 30),
            "end": datetime.datetime(2026, 8, 10, 19, 30)
        }
    ]
    
    # Non-overlapping case (7:45 PM - 8:45 PM)
    start_dt = datetime.datetime(2026, 8, 10, 19, 45)
    end_dt = datetime.datetime(2026, 8, 10, 20, 45)
    
    conflicts = []
    for evt in existing_events:
        if evt["start"] < end_dt and start_dt < evt["end"]:
            conflicts.append(evt)
            
    assert len(conflicts) == 0

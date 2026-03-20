"""ICS calendar generation for notes with due dates."""

from datetime import timedelta
from icalendar import Calendar, Event, Alarm
from notes.models import Note, Priority


PRIORITY_ICAL_MAP = {
    Priority.URGENT: 1,
    Priority.HIGH: 3,
    Priority.MEDIUM: 5,
    Priority.LOW: 9,
}


def generate_ics(notes: list[Note]) -> str:
    """Generate an ICS calendar string from a list of notes."""
    cal = Calendar()
    cal.add("prodid", "-//NoteManager//notes//CN")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", "Notes Calendar")
    cal.add("x-wr-timezone", "Asia/Shanghai")

    for note in notes:
        event = Event()
        summary = note.title or note.content[:50]
        event.add("summary", summary)
        event.add("description", note.content)
        event.add("uid", f"note-{note.id}@notemanager")

        if note.due_date:
            event.add("dtstart", note.due_date)
            event.add("dtend", note.due_date + timedelta(days=1))
        elif note.created_at:
            event.add("dtstart", note.created_at.date())
            event.add("dtend", note.created_at.date() + timedelta(days=1))

        event.add("priority", PRIORITY_ICAL_MAP.get(note.priority, 5))

        if note.tags:
            event.add("categories", note.tags)

        if note.is_done:
            event.add("status", "COMPLETED")
        else:
            event.add("status", "NEEDS-ACTION")

        if note.created_at:
            event.add("created", note.created_at)

        # Add alarm for high/urgent priority notes (1 hour before)
        if note.priority in (Priority.URGENT, Priority.HIGH) and not note.is_done:
            alarm = Alarm()
            alarm.add("action", "DISPLAY")
            alarm.add("description", f"Reminder: {summary}")
            alarm.add("trigger", timedelta(hours=-1))
            event.add_component(alarm)

        cal.add_component(event)

    return cal.to_ical().decode("utf-8")

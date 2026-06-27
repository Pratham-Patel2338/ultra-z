from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Reminder
from app.schemas.reminder import ReminderCreate, ReminderUpdate


def create_reminder(session: Session, payload: ReminderCreate) -> Reminder:
    reminder = Reminder(
        title=payload.title,
        note=payload.note,
        due_at=payload.due_at,
        is_done=payload.is_done,
    )
    session.add(reminder)
    session.commit()
    session.refresh(reminder)
    return reminder


def update_reminder(session: Session, reminder: Reminder, payload: ReminderUpdate) -> Reminder:
    if payload.title is not None:
        reminder.title = payload.title
    if payload.note is not None:
        reminder.note = payload.note
    if payload.due_at is not None:
        reminder.due_at = payload.due_at
    if payload.is_done is not None:
        reminder.is_done = payload.is_done

    session.commit()
    session.refresh(reminder)
    return reminder


def delete_reminder(session: Session, reminder: Reminder) -> None:
    session.delete(reminder)
    session.commit()


def list_reminders(session: Session, only_open: bool = False) -> list[Reminder]:
    statement = select(Reminder).order_by(Reminder.created_at.desc())
    if only_open:
        statement = statement.where(Reminder.is_done.is_(False))
    return list(session.scalars(statement).all())


def get_reminder(session: Session, reminder_id: int) -> Reminder | None:
    return session.get(Reminder, reminder_id)

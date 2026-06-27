from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_subject, get_database_session
from app.schemas.reminder import ReminderCreate, ReminderRead, ReminderUpdate
from app.services.reminders import create_reminder, delete_reminder, get_reminder, list_reminders, update_reminder

router = APIRouter()


@router.get("", response_model=list[ReminderRead])
def read_reminders(
    only_open: bool = False,
    session: Session = Depends(get_database_session),
    subject: str = Depends(get_current_subject),
) -> list[ReminderRead]:
    _ = subject
    return [ReminderRead.model_validate(item) for item in list_reminders(session, only_open=only_open)]


@router.post("", response_model=ReminderRead, status_code=status.HTTP_201_CREATED)
def create_reminder_item(
    payload: ReminderCreate,
    session: Session = Depends(get_database_session),
    subject: str = Depends(get_current_subject),
) -> ReminderRead:
    _ = subject
    reminder = create_reminder(session, payload)
    return ReminderRead.model_validate(reminder)


@router.get("/{reminder_id}", response_model=ReminderRead)
def read_reminder(
    reminder_id: int,
    session: Session = Depends(get_database_session),
    subject: str = Depends(get_current_subject),
) -> ReminderRead:
    _ = subject
    reminder = get_reminder(session, reminder_id)
    if reminder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
    return ReminderRead.model_validate(reminder)


@router.patch("/{reminder_id}", response_model=ReminderRead)
def update_reminder_item(
    reminder_id: int,
    payload: ReminderUpdate,
    session: Session = Depends(get_database_session),
    subject: str = Depends(get_current_subject),
) -> ReminderRead:
    _ = subject
    reminder = get_reminder(session, reminder_id)
    if reminder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
    updated = update_reminder(session, reminder, payload)
    return ReminderRead.model_validate(updated)


@router.delete("/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reminder_item(
    reminder_id: int,
    session: Session = Depends(get_database_session),
    subject: str = Depends(get_current_subject),
) -> None:
    _ = subject
    reminder = get_reminder(session, reminder_id)
    if reminder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
    delete_reminder(session, reminder)

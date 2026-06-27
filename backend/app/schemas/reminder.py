from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReminderCreate(BaseModel):
    title: str = Field(min_length=1)
    note: str | None = None
    due_at: datetime | None = None
    is_done: bool = False


class ReminderUpdate(BaseModel):
    title: str | None = None
    note: str | None = None
    due_at: datetime | None = None
    is_done: bool | None = None


class ReminderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    note: str | None
    due_at: datetime | None
    is_done: bool
    created_at: datetime
    updated_at: datetime

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MemoryCreate(BaseModel):
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    namespace: str = Field(default="default")
    tags: list[str] = Field(default_factory=list)
    source: str = Field(default="manual")


class MemoryUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    namespace: str | None = None
    tags: list[str] | None = None
    source: str | None = None


class MemoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content: str
    namespace: str
    tags: list[str] = Field(default_factory=list)
    source: str
    created_at: datetime
    updated_at: datetime

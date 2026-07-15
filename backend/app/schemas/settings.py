from pydantic import BaseModel, Field


class AppSettingsRead(BaseModel):
    model: str
    voice: str
    theme: str = "Dark"
    wakeword_enabled: bool = Field(alias="wakewordEnabled")
    volume: int = 80
    temperature: float = 0.2


class AppSettingsUpdate(BaseModel):
    model: str | None = None
    voice: str | None = None
    theme: str | None = None
    wakeword_enabled: bool | None = Field(default=None, alias="wakewordEnabled")
    volume: int | None = None
    temperature: float | None = None

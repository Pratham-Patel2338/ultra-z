from pydantic import BaseModel, Field


class VoiceTranscriptionResponse(BaseModel):
    transcript: str = Field(..., description="Transcribed text")
    language: str | None = Field(default=None, description="Detected language code")
    confidence: float | None = Field(default=None, ge=0.0, le=1.0, description="Language detection confidence")

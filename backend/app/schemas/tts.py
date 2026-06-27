from typing import Literal

from pydantic import BaseModel, Field

TTSLanguage = Literal["auto", "en", "hi", "gu"]
TTSVoice = Literal["auto", "english", "hindi", "gujarati"]


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000, description="Text to synthesize")
    voice: TTSVoice = Field(default="auto", description="Voice selection")
    language: TTSLanguage = Field(default="auto", description="Optional language hint")


class TTSGenerationMeta(BaseModel):
    voice: str
    language: str | None = None
    cached: bool = False
    sample_rate: int | None = None
    file_name: str | None = None

from pydantic import BaseModel, ConfigDict, Field


class PinLoginRequest(BaseModel):
    pin: str = Field(min_length=1)


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
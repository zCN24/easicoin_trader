from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    code: int = Field(..., examples=[40001])
    message: str = Field(..., min_length=1, examples=["Invalid signature"])
    request_id: str | None = Field(default=None, examples=["req_123456"])

    @classmethod
    def from_dict(cls, data: dict) -> "ErrorResponse":
        return cls.model_validate(data)

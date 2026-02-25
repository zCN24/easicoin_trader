from __future__ import annotations

from pydantic import BaseModel, Field


class AccountBalance(BaseModel):
    asset: str = Field(..., min_length=1, examples=["USDT"])
    available: float = Field(..., ge=0, examples=[1200.5])
    locked: float = Field(default=0.0, ge=0, examples=[0.0])
    total: float = Field(..., ge=0, examples=[1200.5])

    @classmethod
    def from_dict(cls, data: dict) -> "AccountBalance":
        return cls.model_validate(data)

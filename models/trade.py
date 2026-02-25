from __future__ import annotations

from pydantic import BaseModel, Field


class Trade(BaseModel):
    trade_id: str = Field(..., min_length=1, examples=["T987654321"])
    symbol: str = Field(..., min_length=1, examples=["BTCUSDT"])
    price: float = Field(..., gt=0, examples=[68010.2])
    size: float = Field(..., gt=0, examples=[0.01])
    side: str = Field(..., min_length=1, examples=["buy"])
    timestamp: int = Field(..., examples=[1700000000000])

    @classmethod
    def from_dict(cls, data: dict) -> "Trade":
        return cls.model_validate(data)

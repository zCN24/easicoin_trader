from __future__ import annotations

from pydantic import BaseModel, Field


class Ticker(BaseModel):
    symbol: str = Field(..., min_length=1, examples=["BTCUSDT"])
    last_price: float = Field(..., gt=0, examples=[68010.2])
    index_price: float = Field(..., gt=0, examples=[67990.4])
    funding_rate: float = Field(..., examples=[0.0001])
    mark_price: float | None = Field(default=None, gt=0, examples=[68005.1])
    timestamp: int | None = Field(default=None, examples=[1700000000000])

    @classmethod
    def from_dict(cls, data: dict) -> "Ticker":
        return cls.model_validate(data)

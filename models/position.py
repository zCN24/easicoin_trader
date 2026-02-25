from __future__ import annotations

from pydantic import BaseModel, Field


class Position(BaseModel):
    symbol: str = Field(..., min_length=1, examples=["BTCUSDT"])
    size: float = Field(..., examples=[0.02])
    entry_price: float = Field(..., gt=0, examples=[65000.0])
    unrealized_pnl: float = Field(..., examples=[12.34])
    leverage: float = Field(default=1.0, ge=1.0, examples=[10.0])
    liquidation_price: float | None = Field(default=None, examples=[59000.0])

    @classmethod
    def from_dict(cls, data: dict) -> "Position":
        return cls.model_validate(data)

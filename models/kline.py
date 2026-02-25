from __future__ import annotations

from pydantic import BaseModel, Field


class Kline(BaseModel):
    symbol: str = Field(..., min_length=1, examples=["BTCUSDT"])
    interval: str = Field(..., min_length=1, examples=["1m"])
    start_time: int = Field(..., examples=[1700000000000])
    end_time: int = Field(..., examples=[1700000059999])
    open: float = Field(..., gt=0, examples=[68000.0])
    high: float = Field(..., gt=0, examples=[68100.0])
    low: float = Field(..., gt=0, examples=[67950.0])
    close: float = Field(..., gt=0, examples=[68050.0])
    volume: float = Field(..., ge=0, examples=[12.34])
    turnover: float | None = Field(default=None, ge=0, examples=[839000.0])

    @classmethod
    def from_dict(cls, data: dict) -> "Kline":
        return cls.model_validate(data)

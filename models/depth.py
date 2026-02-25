from __future__ import annotations

from pydantic import BaseModel, Field


class DepthLevel(BaseModel):
    price: float = Field(..., gt=0, examples=[68000.1])
    size: float = Field(..., gt=0, examples=[0.5])

    @classmethod
    def from_dict(cls, data: dict) -> "DepthLevel":
        return cls.model_validate(data)


class Depth(BaseModel):
    symbol: str = Field(..., min_length=1, examples=["BTCUSDT"])
    bids: list[DepthLevel] = Field(default_factory=list, examples=[[{"price": 68000.1, "size": 0.5}]])
    asks: list[DepthLevel] = Field(default_factory=list, examples=[[{"price": 68001.2, "size": 0.3}]])
    timestamp: int | None = Field(default=None, examples=[1700000000000])

    @classmethod
    def from_dict(cls, data: dict) -> "Depth":
        return cls.model_validate(data)

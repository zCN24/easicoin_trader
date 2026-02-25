from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class OrderSide(str, Enum):
    buy = "buy"
    sell = "sell"


class OrderStatus(str, Enum):
    new = "new"
    filled = "filled"
    canceled = "canceled"


class Order(BaseModel):
    order_id: str = Field(..., min_length=1, examples=["A123456789"])
    symbol: str = Field(..., min_length=1, examples=["BTCUSDT"])
    side: OrderSide = Field(..., examples=["buy"])
    price: float = Field(..., gt=0, examples=[68000.5])
    size: float = Field(..., gt=0, examples=[0.01])
    status: OrderStatus = Field(..., examples=["new"])

    @classmethod
    def from_dict(cls, data: dict) -> "Order":
        return cls.model_validate(data)

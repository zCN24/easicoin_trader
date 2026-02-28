from __future__ import annotations

from typing import Any, Optional

from core.api_client import EasiCoinClient
from models.order import Order, OrderSide


class OrderService:
    def __init__(self, client: EasiCoinClient) -> None:
        self._client = client

    async def place_limit_order(
        self,
        symbol: str,
        side: OrderSide,
        price: float,
        qty: float,
        position_idx: int = 1,
        time_in_force: str = "GoodTillCancel",
        reduce_only: bool = False,
        order_link_id: Optional[str] = None,
    ) -> Order:
        if not symbol:
            raise ValueError("symbol 不能为空")
        if price <= 0:
            raise ValueError("price 必须大于 0")
        if qty <= 0:
            raise ValueError("qty 必须大于 0")

        payload: dict[str, Any] = {
            "symbol": symbol,
            "side": side.value.capitalize(),
            "position_idx": position_idx,
            "order_type": "Limit",
            "price": str(price),
            "qty": str(qty),
            "time_in_force": time_in_force,
            "reduce_only": reduce_only,
        }
        if order_link_id:
            payload["order_link_id"] = order_link_id

        data = await self._client.create_order(payload)
        return Order.model_validate(data)

    async def place_market_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: float,
        position_idx: int = 1,
        reduce_only: bool = False,
        order_link_id: Optional[str] = None,
    ) -> Order:
        if not symbol:
            raise ValueError("symbol 不能为空")
        if qty <= 0:
            raise ValueError("qty 必须大于 0")

        payload: dict[str, Any] = {
            "symbol": symbol,
            "side": side.value.capitalize(),
            "position_idx": position_idx,
            "order_type": "Market",
            "qty": str(qty),
            "reduce_only": reduce_only,
        }
        if order_link_id:
            payload["order_link_id"] = order_link_id

        data = await self._client.create_order(payload)
        return Order.model_validate(data)

    async def cancel_order(self, order_id: str) -> Order:
        """撤销单个订单。

        参数:
            order_id: 订单 ID。

        返回:
            Order: 撤单结果。
        """
        if not order_id:
            raise ValueError("order_id 不能为空")

        data = await self._client.cancel_order({"order_id": order_id})
        return Order.model_validate(data)

    async def cancel_all(self, symbol: Optional[str] = None) -> list[Order]:
        """撤销全部订单，可按交易对过滤。

        参数:
            symbol: 交易对，可选。

        返回:
            list[Order]: 撤单结果列表。
        """
        payload: dict[str, Any] = {}
        if symbol:
            payload["symbol"] = symbol
        data = await self._client.cancel_all_orders(payload)
        if isinstance(data, dict) and "list" in data:
            data = data["list"]
        return [Order.model_validate(item) for item in data]

    async def get_open_orders(self, symbol: Optional[str] = None, limit: int = 50) -> list[Order]:
        """查询当前未成交订单。

        参数:
            symbol: 交易对，可选。
            limit: 返回数量，必须大于 0。

        返回:
            list[Order]: 未成交订单列表。
        """
        if limit <= 0:
            raise ValueError("limit 必须大于 0")

        params: dict[str, Any] = {"limit": limit}
        if symbol:
            params["symbol"] = symbol
        data = await self._client.get_activity_orders(params)
        items = data.get("list", []) if isinstance(data, dict) else data
        return [Order.model_validate(item) for item in items]

    async def get_order_history(
        self,
        symbol: Optional[str] = None,
        limit: int = 50,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> list[Order]:
        """查询历史订单。

        参数:
            symbol: 交易对，可选。
            limit: 返回数量，必须大于 0。
            start_time: 开始时间戳（毫秒），可选。
            end_time: 结束时间戳（毫秒），可选。

        返回:
            list[Order]: 历史订单列表。
        """
        if limit <= 0:
            raise ValueError("limit 必须大于 0")
        if start_time is not None and start_time < 0:
            raise ValueError("start_time 不能小于 0")
        if end_time is not None and end_time < 0:
            raise ValueError("end_time 不能小于 0")
        if start_time is not None and end_time is not None and start_time > end_time:
            raise ValueError("start_time 不能大于 end_time")

        params: dict[str, Any] = {"limit": limit}
        if symbol:
            params["symbol"] = symbol
        if start_time is not None:
            params["start_time"] = start_time
        if end_time is not None:
            params["end_time"] = end_time

        data = await self._client.get_orders(params)
        items = data.get("list", []) if isinstance(data, dict) else data
        return [Order.model_validate(item) for item in items]

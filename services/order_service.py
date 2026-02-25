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
        size: float,
        time_in_force: str = "GTC",
        reduce_only: bool = False,
        client_order_id: Optional[str] = None,
    ) -> Order:
        """下限价单。

        参数:
            symbol: 交易对，例如 BTCUSDT。
            side: 方向，buy 或 sell。
            price: 限价价格，必须大于 0。
            size: 下单数量，必须大于 0。
            time_in_force: 订单生效策略，常见 GTC/IOC/FOK。
            reduce_only: 是否只减仓。
            client_order_id: 自定义订单 ID，可选。

        返回:
            Order: 下单结果。
        """
        if not symbol:
            raise ValueError("symbol 不能为空")
        if price <= 0:
            raise ValueError("price 必须大于 0")
        if size <= 0:
            raise ValueError("size 必须大于 0")
        if not time_in_force:
            raise ValueError("time_in_force 不能为空")

        payload: dict[str, Any] = {
            "symbol": symbol,
            "side": side.value,
            "type": "limit",
            "price": price,
            "size": size,
            "timeInForce": time_in_force,
            "reduceOnly": reduce_only,
        }
        if client_order_id:
            payload["clientOrderId"] = client_order_id

        data = await self._client.post("order/place", data=payload)
        return Order.model_validate(data)

    async def place_market_order(
        self,
        symbol: str,
        side: OrderSide,
        size: float,
        reduce_only: bool = False,
        client_order_id: Optional[str] = None,
    ) -> Order:
        """下市价单。

        参数:
            symbol: 交易对。
            side: 方向，buy 或 sell。
            size: 下单数量，必须大于 0。
            reduce_only: 是否只减仓。
            client_order_id: 自定义订单 ID，可选。

        返回:
            Order: 下单结果。
        """
        if not symbol:
            raise ValueError("symbol 不能为空")
        if size <= 0:
            raise ValueError("size 必须大于 0")

        payload: dict[str, Any] = {
            "symbol": symbol,
            "side": side.value,
            "type": "market",
            "size": size,
            "reduceOnly": reduce_only,
        }
        if client_order_id:
            payload["clientOrderId"] = client_order_id

        data = await self._client.post("order/place", data=payload)
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

        data = await self._client.post("order/cancel", data={"orderId": order_id})
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
        data = await self._client.post("order/cancel-all", data=payload)
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
        data = await self._client.get("order/open-orders", params=params)
        return [Order.model_validate(item) for item in data]

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
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time

        data = await self._client.get("order/history", params=params)
        return [Order.model_validate(item) for item in data]

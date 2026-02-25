from __future__ import annotations

from typing import Any, Optional

from core.api_client import EasiCoinClient
from models.depth import Depth
from models.kline import Kline
from models.market import Ticker
from models.trade import Trade


class MarketService:
    def __init__(self, client: EasiCoinClient) -> None:
        self._client = client

    async def get_tickers(self) -> list[Ticker]:
        """获取全市场行情。

        返回:
            list[Ticker]: 行情列表。
        """
        data = await self._client.get("market/tickers")
        return [Ticker.model_validate(item) for item in data]

    async def get_depth(self, symbol: str, limit: int = 20) -> Depth:
        """获取深度行情。

        参数:
            symbol: 交易对。
            limit: 档位数量，必须大于 0。

        返回:
            Depth: 深度数据。
        """
        if not symbol:
            raise ValueError("symbol 不能为空")
        if limit <= 0:
            raise ValueError("limit 必须大于 0")

        params: dict[str, Any] = {"symbol": symbol, "limit": limit}
        data = await self._client.get("market/depth", params=params)
        return Depth.model_validate(data)

    async def get_kline(
        self,
        symbol: str,
        interval: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> list[Kline]:
        """获取 K 线数据。

        参数:
            symbol: 交易对。
            interval: K 线周期，例如 1m/5m/1h。
            start_time: 开始时间戳（毫秒），可选。
            end_time: 结束时间戳（毫秒），可选。
            limit: 返回数量，可选。

        返回:
            list[Kline]: K 线列表。
        """
        if not symbol:
            raise ValueError("symbol 不能为空")
        if not interval:
            raise ValueError("interval 不能为空")
        if start_time is not None and start_time < 0:
            raise ValueError("start_time 不能小于 0")
        if end_time is not None and end_time < 0:
            raise ValueError("end_time 不能小于 0")
        if limit is not None and limit <= 0:
            raise ValueError("limit 必须大于 0")

        params: dict[str, Any] = {"symbol": symbol, "interval": interval}
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        if limit is not None:
            params["limit"] = limit

        data = await self._client.get("market/kline", params=params)
        return [Kline.model_validate(item) for item in data]

    async def get_trades(self, symbol: str, limit: int = 50) -> list[Trade]:
        """获取最新成交。

        参数:
            symbol: 交易对。
            limit: 返回数量，必须大于 0。

        返回:
            list[Trade]: 成交列表。
        """
        if not symbol:
            raise ValueError("symbol 不能为空")
        if limit <= 0:
            raise ValueError("limit 必须大于 0")

        params: dict[str, Any] = {"symbol": symbol, "limit": limit}
        data = await self._client.get("market/trades", params=params)
        return [Trade.model_validate(item) for item in data]

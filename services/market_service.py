from __future__ import annotations

from typing import Any, Optional

from core.api_client import EasiCoinClient
from models.depth import Depth, DepthLevel
from models.kline import Kline
from models.market import Ticker
from models.trade import Trade


class MarketService:
    def __init__(self, client: EasiCoinClient) -> None:
        self._client = client

    async def get_tickers(self, symbol: Optional[str] = None) -> list[Ticker]:
        """获取全市场 ticker。"""
        raw = await self._client.get_tickers(symbol)
        items = raw.get("list", []) if isinstance(raw, dict) else raw
        result: list[Ticker] = []
        for item in items:
            result.append(
                Ticker(
                    symbol=item.get("symbol", ""),
                    last_price=float(item.get("last_price", 0) or item.get("lastPrice", 0)),
                    index_price=float(item.get("index_price", 0) or item.get("indexPrice", 0)),
                    funding_rate=float(item.get("funding_rate", 0) or item.get("fundingRate", 0)),
                    mark_price=float(item.get("mark_price", 0) or item.get("markPrice", 0)) if item.get("mark_price") or item.get("markPrice") else None,
                    timestamp=int(item.get("time", 0)) if item.get("time") else None,
                )
            )
        return result

    async def get_depth(self, symbol: str, limit: int = 20) -> Depth:
        """获取订单簿深度 (最大 25 档)。"""
        if not symbol:
            raise ValueError("symbol 不能为空")
        if limit <= 0 or limit > 25:
            raise ValueError("limit 必须在 1-25 之间")

        raw = await self._client.get_depth(symbol, depth=limit)
        bids = [DepthLevel(price=float(p), size=float(s)) for p, s in raw.get("b", [])]
        asks = [DepthLevel(price=float(p), size=float(s)) for p, s in raw.get("a", [])]
        return Depth(symbol=raw.get("s", symbol), bids=bids, asks=asks, timestamp=int(raw.get("ts", 0)) or None)

    async def get_kline(
        self,
        symbol: str,
        interval: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 100,
    ) -> list[Kline]:
        if not symbol:
            raise ValueError("symbol 不能为空")
        if not interval:
            raise ValueError("interval 不能为空")
        raw = await self._client.get_kline(symbol, interval, start=start_time, end=end_time, limit=limit)
        rows = raw.get("list", []) if isinstance(raw, dict) else raw
        klines: list[Kline] = []
        for entry in rows:
            start = int(entry[0])
            open_p, high_p, low_p, close_p = map(float, entry[1:5])
            volume = float(entry[5]) if len(entry) > 5 else 0.0
            turnover = float(entry[6]) if len(entry) > 6 else None
            klines.append(
                Kline(
                    symbol=symbol,
                    interval=interval,
                    start_time=start,
                    end_time=start,  # API未返回 end，使用 start 占位
                    open=open_p,
                    high=high_p,
                    low=low_p,
                    close=close_p,
                    volume=volume,
                    turnover=turnover,
                )
            )
        return klines

    async def get_trades(self, symbol: str, limit: int = 50) -> list[Trade]:
        if not symbol:
            raise ValueError("symbol 不能为空")
        if limit <= 0 or limit > 100:
            raise ValueError("limit 必须在 1-100 之间")

        raw = await self._client.get_trades(symbol, limit=limit)
        items = raw.get("items", []) if isinstance(raw, dict) else raw
        trades: list[Trade] = []
        for idx, item in enumerate(items):
            trades.append(
                Trade(
                    trade_id=str(item.get("exec_id") or item.get("trade_id") or f"{item.get('exec_time')}-{idx}"),
                    symbol=symbol,
                    price=float(item.get("exec_price")),
                    size=float(item.get("exec_qty")),
                    side=item.get("side", "").lower(),
                    timestamp=int(item.get("exec_time", 0)) * 1000,
                )
            )
        return trades

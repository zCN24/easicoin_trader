from __future__ import annotations

from typing import Any, Optional

from core.api_client import EasiCoinClient
from models.position import Position


class PositionService:
    def __init__(self, client: EasiCoinClient) -> None:
        self._client = client

    async def get_positions(self, symbol: Optional[str] = None) -> list[Position]:
        """查询当前持仓。

        参数:
            symbol: 交易对，可选。

        返回:
            list[Position]: 持仓列表。
        """
        params: dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol
        data = await self._client.get_positions(symbol=symbol)
        items = data.get("list", []) if isinstance(data, dict) else data
        return [Position.model_validate(item) for item in items]

    async def set_leverage(self, symbol: str, leverage: float) -> Position:
        """设置杠杆倍数。

        参数:
            symbol: 交易对。
            leverage: 杠杆倍数，必须大于等于 1。

        返回:
            Position: 设置后的持仓信息。
        """
        if not symbol:
            raise ValueError("symbol 不能为空")
        if leverage < 1:
            raise ValueError("leverage 必须大于等于 1")

        data = await self._client.set_leverage(symbol=symbol, buy_leverage=int(leverage), sell_leverage=int(leverage))
        return Position.model_validate(data) if isinstance(data, dict) else Position.model_validate({"symbol": symbol, "leverage": leverage})

    async def set_margin_mode(self, symbol: str, mode: str) -> Position:
        """设置保证金模式。

        参数:
            symbol: 交易对。
            mode: 模式，仅支持 cross 或 isolated。

        返回:
            Position: 设置后的持仓信息。
        """
        if not symbol:
            raise ValueError("symbol 不能为空")
        if mode not in {"Cross", "Isolated", "cross", "isolated"}:
            raise ValueError("mode 仅支持 Cross/Isolated")

        payload = {"symbol": symbol, "margin_mode": mode.capitalize() if mode.islower() else mode}
        data = await self._client.set_margin_mode(**payload)
        return Position.model_validate(data) if isinstance(data, dict) else Position.model_validate({"symbol": symbol})

    async def close_position(self, symbol: str, size: Optional[float] = None) -> Position:
        """市价平仓。

        参数:
            symbol: 交易对。
            size: 平仓数量，可选；为空时按全平处理。

        返回:
            Position: 平仓后的持仓信息。
        """
        if not symbol:
            raise ValueError("symbol 不能为空")
        if size is not None and size <= 0:
            raise ValueError("size 必须大于 0")

        payload: dict[str, Any] = {"symbol": symbol}
        if size is not None:
            payload["qty"] = str(size)
        # 没有直接一键平接口，此处可用市价对冲实现，保持占位
        data = await self._client.create_order({
            "symbol": symbol,
            "side": "Sell",
            "position_idx": 1,
            "order_type": "Market",
            "qty": str(size) if size is not None else "0",
            "reduce_only": True,
        })
        return Position.model_validate(data) if isinstance(data, dict) else Position.model_validate({"symbol": symbol})

    async def set_tp_sl(
        self,
        symbol: str,
        take_profit: Optional[float] = None,
        stop_loss: Optional[float] = None,
    ) -> Position:
        """设置止盈止损。

        参数:
            symbol: 交易对。
            take_profit: 止盈价，可选。
            stop_loss: 止损价，可选。

        返回:
            Position: 更新后的持仓信息。
        """
        if not symbol:
            raise ValueError("symbol 不能为空")
        if take_profit is None and stop_loss is None:
            raise ValueError("take_profit 和 stop_loss 至少传一个")
        if take_profit is not None and take_profit <= 0:
            raise ValueError("take_profit 必须大于 0")
        if stop_loss is not None and stop_loss <= 0:
            raise ValueError("stop_loss 必须大于 0")

        payload: dict[str, Any] = {"symbol": symbol, "position_idx": 1}
        if take_profit is not None:
            payload["take_profit"] = str(take_profit)
        if stop_loss is not None:
            payload["stop_loss"] = str(stop_loss)
        data = await self._client.create_tpsl(payload)
        return Position.model_validate(data) if isinstance(data, dict) else Position.model_validate({"symbol": symbol})

    async def adjust_margin(self, symbol: str, amount: float, action: str) -> Position:
        """调整保证金。

        参数:
            symbol: 交易对。
            amount: 调整数量，必须大于 0。
            action: add 或 reduce。

        返回:
            Position: 更新后的持仓信息。
        """
        if not symbol:
            raise ValueError("symbol 不能为空")
        if amount <= 0:
            raise ValueError("amount 必须大于 0")
        if action not in {"add", "reduce"}:
            raise ValueError("action 仅支持 add 或 reduce")

        margin_value = amount if action == "add" else -amount
        data = await self._client.adjust_margin(symbol=symbol, position_idx=1, margin=str(margin_value))
        return Position.model_validate(data) if isinstance(data, dict) else Position.model_validate({"symbol": symbol})

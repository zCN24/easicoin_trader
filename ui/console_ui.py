from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Optional

from rich.align import Align
from rich.console import RenderableType
from rich.panel import Panel
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Input, Static

from core.api_client import EasiCoinClient
from services.market_service import MarketService
from services.order_service import OrderService
from services.position_service import PositionService


@dataclass
class TickerRow:
    symbol: str
    last: float
    change: float


@dataclass
class DepthLevel:
    price: float
    size: float


@dataclass
class PositionRow:
    symbol: str
    size: float
    entry: float
    pnl: float


class KlinePanel(Static):
    def __init__(self) -> None:
        super().__init__(id="kline")
        self._series: list[float] = [random.uniform(65000, 68000) for _ in range(40)]

    def push_price(self, price: float) -> None:
        self._series.append(price)
        if len(self._series) > 60:
            self._series.pop(0)
        self.refresh()

    def render(self) -> RenderableType:
        values = self._series
        if not values:
            return Panel("No data", title="Kline", border_style="cyan")
        min_v = min(values)
        max_v = max(values)
        span = max(max_v - min_v, 1)
        height = 12
        width = len(values)
        grid = [[" " for _ in range(width)] for _ in range(height)]
        for x, v in enumerate(values):
            level = int((v - min_v) / span * (height - 1))
            y = height - 1 - level
            grid[y][x] = "█"
        lines = ["".join(row) for row in grid]
        text = Text("\n".join(lines), style="bold green")
        return Panel(Align.center(text), title="Kline", border_style="cyan")


class EasiCoinTerminal(App[None]):
    CSS = """
    Screen {
        background: #0b1014;
        color: #d9e3ea;
    }
    #root {
        height: 1fr;
    }
    #status {
        height: 3;
        content-align: center middle;
        border: solid #2b3a42;
        background: #111a21;
    }
    #left {
        width: 34%;
        border: solid #26323a;
    }
    #center {
        width: 36%;
        border: solid #26323a;
    }
    #right {
        width: 30%;
        border: solid #26323a;
    }
    #cmd {
        height: 3;
        border: solid #2b3a42;
        background: #0f151b;
    }
    DataTable {
        height: 1fr;
        background: #0f151b;
    }
    """

    BINDINGS = [("q", "quit", "退出")]

    client: Optional[EasiCoinClient] = None
    market_service: Optional[MarketService] = None
    order_service: Optional[OrderService] = None
    position_service: Optional[PositionService] = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(id="status")
        with Horizontal(id="root"):
            with Vertical(id="left"):
                yield Static("市场", classes="section-title")
                yield DataTable(id="tickers")
                yield Static("深度", classes="section-title")
                yield DataTable(id="depth")
            with Vertical(id="center"):
                yield KlinePanel()
            with Vertical(id="right"):
                yield Static("订单簿", classes="section-title")
                yield DataTable(id="orderbook")
                yield Static("我的持仓", classes="section-title")
                yield DataTable(id="positions")
        yield Input(placeholder="buy 0.01 BTCUSDT @ market | close all | leverage 20", id="cmd")
        yield Footer()

    async def on_mount(self) -> None:
        self._setup_tables()
        self._last_price = 0.0
        self._balance = 0.0
        self._leverage = 0
        self._conn_status = "connecting"
        self._positions: list[PositionRow] = []
        self._tickers: list[TickerRow] = []
        self._depth: tuple[list[DepthLevel], list[DepthLevel]] = ([], [])
        await self._pull_market()
        self.set_interval(5, lambda: asyncio.create_task(self._pull_market()))
        self._refresh_ui()

    def _setup_tables(self) -> None:
        tickers = self.query_one("#tickers", DataTable)
        tickers.clear(columns=True)
        tickers.add_columns("交易对", "最新价", "涨跌幅")

        depth = self.query_one("#depth", DataTable)
        depth.clear(columns=True)
        depth.add_columns("买价", "买量", "卖价", "卖量")

        book = self.query_one("#orderbook", DataTable)
        book.clear(columns=True)
        book.add_columns("买价", "买量", "卖价", "卖量")

        positions = self.query_one("#positions", DataTable)
        positions.clear(columns=True)
        positions.add_columns("交易对", "持仓量", "开仓价", "盈亏")

    async def _pull_market(self) -> None:
        """拉取行情与持仓，失败时保持现有数据。"""
        if self.market_service is None:
            return
        try:
            tickers = await self.market_service.get_tickers()
            self._tickers = [TickerRow(t.symbol, t.last_price, 0.0) for t in tickers]
            top_symbol = tickers[0].symbol if tickers else "BTCUSDT"
            depth = await self.market_service.get_depth(top_symbol, limit=20)
            bids = [DepthLevel(float(l.price), float(l.size)) for l in depth.bids]
            asks = [DepthLevel(float(l.price), float(l.size)) for l in depth.asks]
            self._depth = (bids, asks)
            self._last_price = tickers[0].last_price if tickers else self._last_price
            if self.client:
                balance_raw = await self.client.get_account_balance()
                balance_list = balance_raw.get("list", []) if isinstance(balance_raw, dict) else balance_raw
                if balance_list:
                    self._balance = float(balance_list[0].get("available_balance", 0) or balance_list[0].get("availableBalance", 0) or balance_list[0].get("wallet_balance", 0))
            if self.position_service:
                positions = await self.position_service.get_positions()
                self._positions = [
                    PositionRow(
                        p.symbol,
                        p.size,
                        p.entry_price,
                        p.unrealized_pnl,
                    )
                    for p in positions
                ]
            self._conn_status = "connected"
        except Exception as exc:  # pragma: no cover - UI best-effort
            self._conn_status = "error"
            self._notify(f"数据刷新失败: {exc}")

    def _refresh_ui(self) -> None:
        self._update_status()
        self._update_tickers()
        self._update_depth_tables()
        self._update_positions()
        if self._last_price > 0:
            self.query_one(KlinePanel).push_price(self._last_price)

    def _update_status(self) -> None:
        status = self.query_one("#status", Static)
        text = (
            f"资产: {self._balance:.2f} USDT  |  "
            f"持仓数: {len(self._positions)}  |  "
            f"杠杆: {self._leverage}倍  |  "
            f"连接状态: {self._conn_status.upper()}"
        )
        status.update(text)

    def _update_tickers(self) -> None:
        table = self.query_one("#tickers", DataTable)
        table.clear()
        for row in self._tickers:
            change_style = "green" if row.change >= 0 else "red"
            table.add_row(
                row.symbol,
                f"{row.last:.2f}",
                Text(f"{row.change:+.2f}%", style=change_style),
            )

    def _update_depth_tables(self) -> None:
        depth_table = self.query_one("#depth", DataTable)
        book_table = self.query_one("#orderbook", DataTable)
        depth_table.clear()
        book_table.clear()
        bids, asks = self._depth
        for bid, ask in zip(bids, asks, strict=False):
            bid_price = f"{bid.price:.2f}" if bid else ""
            bid_size = f"{bid.size:.3f}" if bid else ""
            ask_price = f"{ask.price:.2f}" if ask else ""
            ask_size = f"{ask.size:.3f}" if ask else ""
            depth_table.add_row(bid_price, bid_size, ask_price, ask_size)
            book_table.add_row(bid_price, bid_size, ask_price, ask_size)

    def _update_positions(self) -> None:
        table = self.query_one("#positions", DataTable)
        table.clear()
        for pos in self._positions:
            pnl_style = "green" if pos.pnl >= 0 else "red"
            table.add_row(
                pos.symbol,
                f"{pos.size:.4f}",
                f"{pos.entry:.2f}",
                Text(f"{pos.pnl:+.2f}", style=pnl_style),
            )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        command = event.value.strip()
        event.input.value = ""
        if not command:
            return
        self._handle_command(command)

    def _handle_command(self, command: str) -> None:
        parts = command.split()
        if not parts:
            return
        keyword = parts[0].lower()
        if keyword == "close" and len(parts) >= 2 and parts[1].lower() == "all":
            self._positions.clear()
            self._notify("已全部平仓")
            return
        if keyword == "leverage" and len(parts) == 2:
            try:
                value = int(parts[1])
            except ValueError:
                self._notify("杠杆输入无效")
                return
            if value <= 0:
                self._notify("杠杆必须为正数")
                return
            self._leverage = value
            self._notify(f"杠杆已设置为 {value}倍")
            return
        if keyword == "buy" or keyword == "sell":
            self._notify(f"已收到订单: {command}")
            return
        self._notify("未知命令")

    def _notify(self, message: str) -> None:
        banner = Panel(Text(message, style="bold #e8c547"), border_style="#2b3a42")
        self.push_screen(NotifyScreen(banner))


class NotifyScreen(Screen):
    DEFAULT_CSS = """
    NotifyScreen {
        align: center middle;
        background: #0b1014;
    }
    #notify-panel {
        width: 60%;
        height: auto;
    }
    """

    def __init__(self, panel: RenderableType) -> None:
        super().__init__()
        self._panel = panel

    def compose(self) -> ComposeResult:
        yield Static(self._panel, id="notify-panel")

    async def on_mount(self) -> None:
        await asyncio.sleep(1.2)
        self.app.pop_screen()


def main() -> None:
    app = EasiCoinTerminal()
    app.run()


if __name__ == "__main__":
    main()

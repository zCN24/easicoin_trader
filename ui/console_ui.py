from __future__ import annotations

import random
from dataclasses import dataclass

from rich.align import Align
from rich.console import RenderableType
from rich.panel import Panel
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Input, Static


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

    BINDINGS = [("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(id="status")
        with Horizontal(id="root"):
            with Vertical(id="left"):
                yield Static("Market", classes="section-title")
                yield DataTable(id="tickers")
                yield Static("Depth", classes="section-title")
                yield DataTable(id="depth")
            with Vertical(id="center"):
                yield KlinePanel()
            with Vertical(id="right"):
                yield Static("Order Book", classes="section-title")
                yield DataTable(id="orderbook")
                yield Static("My Positions", classes="section-title")
                yield DataTable(id="positions")
        yield Input(placeholder="buy 0.01 BTCUSDT @ market | close all | leverage 20", id="cmd")
        yield Footer()

    def on_mount(self) -> None:
        self._setup_tables()
        self._last_price = 67000.0
        self._balance = 1200.5
        self._leverage = 10
        self._conn_status = "connected"
        self._positions: list[PositionRow] = [
            PositionRow("BTCUSDT", 0.01, 66500.0, 12.4),
            PositionRow("ETHUSDT", 0.2, 3500.0, -3.1),
        ]
        self._tickers = self._generate_tickers()
        self._depth = self._generate_depth(self._last_price)
        self.set_interval(0.5, self._refresh_ui)
        self._refresh_ui()

    def _setup_tables(self) -> None:
        tickers = self.query_one("#tickers", DataTable)
        tickers.clear(columns=True)
        tickers.add_columns("Symbol", "Last", "Change")

        depth = self.query_one("#depth", DataTable)
        depth.clear(columns=True)
        depth.add_columns("Bid", "Size", "Ask", "Size")

        book = self.query_one("#orderbook", DataTable)
        book.clear(columns=True)
        book.add_columns("Bid", "Size", "Ask", "Size")

        positions = self.query_one("#positions", DataTable)
        positions.clear(columns=True)
        positions.add_columns("Symbol", "Size", "Entry", "PNL")

    def _generate_tickers(self) -> list[TickerRow]:
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
        base = {
            "BTCUSDT": 67000.0,
            "ETHUSDT": 3500.0,
            "SOLUSDT": 120.0,
            "BNBUSDT": 420.0,
            "XRPUSDT": 0.6,
        }
        rows: list[TickerRow] = []
        for sym in symbols:
            last = base[sym] * (1 + random.uniform(-0.002, 0.002))
            change = random.uniform(-1.8, 1.8)
            rows.append(TickerRow(sym, last, change))
        return rows

    def _generate_depth(self, price: float) -> tuple[list[DepthLevel], list[DepthLevel]]:
        bids = [DepthLevel(price - i * 2, random.uniform(0.1, 1.2)) for i in range(1, 8)]
        asks = [DepthLevel(price + i * 2, random.uniform(0.1, 1.2)) for i in range(1, 8)]
        return bids, asks

    def _refresh_ui(self) -> None:
        self._last_price *= 1 + random.uniform(-0.0006, 0.0006)
        self._tickers = self._generate_tickers()
        self._depth = self._generate_depth(self._last_price)
        self._update_status()
        self._update_tickers()
        self._update_depth_tables()
        self._update_positions()
        self.query_one(KlinePanel).push_price(self._last_price)

    def _update_status(self) -> None:
        status = self.query_one("#status", Static)
        text = (
            f"Balance: {self._balance:.2f} USDT  |  "
            f"Positions: {len(self._positions)}  |  "
            f"Leverage: {self._leverage}x  |  "
            f"Connection: {self._conn_status.upper()}"
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
            depth_table.add_row(f"{bid.price:.2f}", f"{bid.size:.3f}", f"{ask.price:.2f}", f"{ask.size:.3f}")
            book_table.add_row(f"{bid.price:.2f}", f"{bid.size:.3f}", f"{ask.price:.2f}", f"{ask.size:.3f}")

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
            self._notify("All positions closed")
            return
        if keyword == "leverage" and len(parts) == 2:
            try:
                value = int(parts[1])
            except ValueError:
                self._notify("Invalid leverage")
                return
            if value <= 0:
                self._notify("Leverage must be positive")
                return
            self._leverage = value
            self._notify(f"Leverage set to {value}x")
            return
        if keyword == "buy" or keyword == "sell":
            self._notify(f"Order received: {command}")
            return
        self._notify("Unknown command")

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
        await self.sleep(1.2)
        self.app.pop_screen()


def main() -> None:
    app = EasiCoinTerminal()
    app.run()


if __name__ == "__main__":
    main()

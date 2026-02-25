from __future__ import annotations

import asyncio
import csv
import json
import time
from dataclasses import dataclass
from getpass import getpass
from pathlib import Path
from typing import Any

from loguru import logger

from config.settings import settings
from core.api_client import EasiCoinClient
from services.market_service import MarketService
from services.order_service import OrderService
from services.position_service import PositionService
from ui.console_ui import EasiCoinTerminal
from utils.logging import configure_logging


@dataclass
class RiskConfig:
    max_position_ratio: float
    max_total_risk: float


def _setup_logging() -> None:
    configure_logging()
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(log_dir / "app.log", level="INFO", rotation="10 MB", retention="7 days")


def _load_api_credentials() -> tuple[str, str]:
    api_key = settings.api_key.strip()
    api_secret = settings.api_secret.strip()
    if not api_key:
        logger.warning("API Key 为空，将通过安全输入获取（建议使用系统密钥库加密保存）")
        api_key = getpass("API Key: ")
    if not api_secret:
        logger.warning("API Secret 为空，将通过安全输入获取（建议使用系统密钥库加密保存）")
        api_secret = getpass("API Secret: ")
    return api_key, api_secret


def _validate_risk(risk: RiskConfig) -> None:
    if not (0 < risk.max_position_ratio <= 1):
        raise ValueError("单笔最大仓位比例必须在 (0, 1] 之间")
    if not (0 < risk.max_total_risk <= 1):
        raise ValueError("总风险百分比必须在 (0, 1] 之间")


def _append_trade_csv(record: dict[str, Any]) -> None:
    data_dir = Path("data")
    data_dir.mkdir(parents=True, exist_ok=True)
    csv_path = data_dir / "trades.csv"
    is_new = not csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=sorted(record.keys()))
        if is_new:
            writer.writeheader()
        writer.writerow(record)


def _grid_trading_example(
    symbol: str,
    center_price: float,
    grid_step: float,
    levels: int,
    size: float,
) -> list[dict[str, Any]]:
    orders: list[dict[str, Any]] = []
    for i in range(1, levels + 1):
        buy_price = round(center_price - i * grid_step, 4)
        sell_price = round(center_price + i * grid_step, 4)
        orders.append({"symbol": symbol, "side": "buy", "price": buy_price, "size": size})
        orders.append({"symbol": symbol, "side": "sell", "price": sell_price, "size": size})
    return orders


async def _save_positions_snapshot(position_service: PositionService) -> None:
    data_dir = Path("data")
    data_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = data_dir / f"positions_{int(time.time())}.json"
    try:
        positions = await position_service.get_positions()
        payload = [pos.model_dump() for pos in positions]
        snapshot_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2))
        logger.info("持仓快照已保存: {path}", path=str(snapshot_path))
    except Exception as exc:
        logger.error("保存持仓快照失败: {error}", error=str(exc))


async def _bootstrap_services() -> tuple[EasiCoinClient, MarketService, OrderService, PositionService]:
    api_key, api_secret = _load_api_credentials()
    client = EasiCoinClient(api_key=api_key, api_secret=api_secret, base_url=settings.api_base_url)
    market_service = MarketService(client)
    order_service = OrderService(client)
    position_service = PositionService(client)
    await client.connect()
    return client, market_service, order_service, position_service


def main() -> None:
    _setup_logging()
    _ = settings

    risk = RiskConfig(max_position_ratio=0.2, max_total_risk=0.5)
    _validate_risk(risk)
    logger.info(
        "风险控制启用: 单笔最大仓位比例={ratio:.2f}, 总风险百分比={total:.2f}",
        ratio=risk.max_position_ratio,
        total=risk.max_total_risk,
    )

    grid_orders = _grid_trading_example(
        symbol="BTCUSDT",
        center_price=67000.0,
        grid_step=50.0,
        levels=3,
        size=0.01,
    )
    logger.info("网格交易示例生成 {count} 笔挂单", count=len(grid_orders))
    for order in grid_orders:
        _append_trade_csv({
            "timestamp": int(time.time() * 1000),
            "symbol": order["symbol"],
            "side": order["side"],
            "price": order["price"],
            "size": order["size"],
            "tag": "grid_example",
        })

    client = None
    position_service = None
    try:
        client, market_service, order_service, position_service = asyncio.run(_bootstrap_services())
        app = EasiCoinTerminal()
        app.client = client
        app.market_service = market_service
        app.order_service = order_service
        app.position_service = position_service
        app.run()
    except KeyboardInterrupt:
        logger.warning("收到退出信号，准备保存持仓快照")
        try:
            if position_service is not None:
                asyncio.run(_save_positions_snapshot(position_service))
        except Exception:
            logger.warning("保存持仓快照失败（服务未初始化）")
    finally:
        try:
            if client is not None:
                asyncio.run(client.close())
        except Exception:
            logger.warning("关闭客户端失败或未初始化")


if __name__ == "__main__":
    main()

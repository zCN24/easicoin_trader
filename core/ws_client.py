from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any, Optional

import aiohttp
from loguru import logger


@dataclass
class _WSState:
    url: str
    session: Optional[aiohttp.ClientSession] = None
    ws: Optional[aiohttp.ClientWebSocketResponse] = None
    reader_task: Optional[asyncio.Task] = None
    heartbeat_task: Optional[asyncio.Task] = None
    reconnect_task: Optional[asyncio.Task] = None
    subscriptions: set[str] = None
    lock: asyncio.Lock = None


class EasiCoinWSClient:
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        public_url: str = "wss://ws.easicoin.io/contract/public/v1",
        private_url: str = "wss://ws.easicoin.io/contract/private/v1",
        recv_window: int = 5000,
        heartbeat_interval: int = 20,
        reconnect_delay: float = 2.0,
        max_reconnect_delay: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._recv_window = recv_window
        self._heartbeat_interval = heartbeat_interval
        self._reconnect_delay = reconnect_delay
        self._max_reconnect_delay = max_reconnect_delay
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        self._public = _WSState(url=public_url, subscriptions=set(), lock=asyncio.Lock())
        self._private = _WSState(url=private_url, subscriptions=set(), lock=asyncio.Lock())

    async def __aenter__(self) -> "EasiCoinWSClient":
        await self.connect_public()
        await self.connect_private()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    @property
    def queue(self) -> asyncio.Queue[dict[str, Any]]:
        return self._queue

    def _sign_ws(self, expires_ms: int) -> str:
        message = f"GET/realtime{expires_ms}"
        digest = hmac.new(self._api_secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
        return digest

    async def connect_public(self) -> None:
        await self._connect(self._public, require_login=False)

    async def connect_private(self) -> None:
        await self._connect(self._private, require_login=True)

    async def close(self) -> None:
        await asyncio.gather(
            self._close_state(self._public),
            self._close_state(self._private),
        )

    async def _connect(self, state: _WSState, require_login: bool) -> None:
        async with state.lock:
            if state.ws is not None:
                return
            state.session = aiohttp.ClientSession()
            state.ws = await state.session.ws_connect(state.url, heartbeat=None)
            logger.info("WS connected {url}", url=state.url)

            if require_login:
                await self._login(state)

            state.reader_task = asyncio.create_task(self._reader_loop(state))
            state.heartbeat_task = asyncio.create_task(self._heartbeat_loop(state))

            if state.subscriptions:
                await self._send_subscribe(state, list(state.subscriptions))

    async def _close_state(self, state: _WSState) -> None:
        async with state.lock:
            for task in (state.reader_task, state.heartbeat_task, state.reconnect_task):
                if task:
                    task.cancel()
            state.reader_task = None
            state.heartbeat_task = None
            state.reconnect_task = None

            if state.ws is not None:
                await state.ws.close()
                state.ws = None
            if state.session is not None:
                await state.session.close()
                state.session = None
            logger.info("WS closed {url}", url=state.url)

    async def _login(self, state: _WSState) -> None:
        if state.ws is None:
            raise RuntimeError("WS is not connected")
        expires = int((time.time() + 60) * 1000)
        signature = self._sign_ws(expires)
        login_msg = {"op": "auth", "args": [self._api_key, expires, signature]}
        await state.ws.send_json(login_msg)
        logger.info("WS auth sent")

    async def _reader_loop(self, state: _WSState) -> None:
        backoff = self._reconnect_delay
        while True:
            try:
                if state.ws is None:
                    raise RuntimeError("WS is not connected")
                msg = await state.ws.receive()
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    await self._queue.put({"source": state.url, "data": data})
                elif msg.type == aiohttp.WSMsgType.BINARY:
                    await self._queue.put({"source": state.url, "data": msg.data})
                elif msg.type in {aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING}:
                    raise ConnectionError("WS closed")
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    raise ConnectionError("WS error")
            except asyncio.CancelledError:
                return
            except Exception as exc:
                logger.error("WS reader error {error}", error=str(exc))
                await self._schedule_reconnect(state, backoff)
                backoff = min(backoff * 2, self._max_reconnect_delay)

    async def _heartbeat_loop(self, state: _WSState) -> None:
        while True:
            try:
                if state.ws is None:
                    raise RuntimeError("WS is not connected")
                await asyncio.sleep(self._heartbeat_interval)
                await state.ws.send_json({"op": "ping"})
            except asyncio.CancelledError:
                return
            except Exception as exc:
                logger.warning("WS heartbeat error {error}", error=str(exc))
                await self._schedule_reconnect(state, self._reconnect_delay)

    async def _schedule_reconnect(self, state: _WSState, delay: float) -> None:
        if state.reconnect_task and not state.reconnect_task.done():
            return

        async def _reconnect() -> None:
            await self._close_state(state)
            await asyncio.sleep(delay)
            require_login = state is self._private
            await self._connect(state, require_login=require_login)

        state.reconnect_task = asyncio.create_task(_reconnect())

    async def subscribe(self, channel: str, symbol: Optional[str] = None, interval: Optional[str] = None) -> None:
        """订阅频道。

        支持频道: ticker、depth、kline、trade、position、order、account。
        """
        topic = self._build_topic(channel, symbol=symbol, interval=interval)
        state = self._pick_state(channel)
        state.subscriptions.add(topic)
        await self._send_subscribe(state, [topic])

    async def unsubscribe(self, channel: str, symbol: Optional[str] = None, interval: Optional[str] = None) -> None:
        """取消订阅频道。"""
        topic = self._build_topic(channel, symbol=symbol, interval=interval)
        state = self._pick_state(channel)
        if topic in state.subscriptions:
            state.subscriptions.remove(topic)
        await self._send_unsubscribe(state, [topic])

    def _pick_state(self, channel: str) -> _WSState:
        if channel in {"position", "order", "execution", "wallet"}:
            return self._private
        return self._public

    def _build_topic(self, channel: str, symbol: Optional[str], interval: Optional[str]) -> str:
        if channel == "ticker":
            if not symbol:
                raise ValueError("symbol 不能为空")
            return f"tickers-100.{symbol}"
        if channel == "depth":
            if not symbol:
                raise ValueError("symbol 不能为空")
            return f"ob_snap_shot.{symbol}.1"
        if channel == "kline":
            if not symbol:
                raise ValueError("symbol 不能为空")
            if not interval:
                raise ValueError("interval 不能为空")
            return f"candle.{interval}.{symbol}"
        if channel == "trade":
            if not symbol:
                raise ValueError("symbol 不能为空")
            return f"trades-100.{symbol}"
        if channel == "position":
            return "contract.position"
        if channel == "order":
            return "contract.order"
        if channel == "execution":
            return "contract.execution"
        if channel == "wallet":
            return "contract.wallet"
        raise ValueError("未知频道")

    async def _send_subscribe(self, state: _WSState, topics: list[str]) -> None:
        if state.ws is None:
            raise RuntimeError("WS is not connected")
        msg = {"op": "subscribe", "args": topics}
        await state.ws.send_json(msg)

    async def _send_unsubscribe(self, state: _WSState, topics: list[str]) -> None:
        if state.ws is None:
            raise RuntimeError("WS is not connected")
        msg = {"op": "unsubscribe", "args": topics}
        await state.ws.send_json(msg)

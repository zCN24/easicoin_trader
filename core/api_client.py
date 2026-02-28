from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from typing import Any, Optional
from urllib.parse import urlencode

import aiohttp
from loguru import logger


class EasiCoinClient:
    """Async REST client for EasiCoin contract API.

    Implements authentication per official docs:
    Access-Sign = HMAC_SHA256(secret, timestamp + Access-Key + Recv-Window + payload)
    payload: GET => raw querystring; POST => raw json body string.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = "https://api.easicoin.io",
        recv_window: int = 5000,
        timeout: float = 10.0,
        max_retries: int = 3,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._api_secret = api_secret
        self._recv_window = recv_window
        self._timeout = timeout
        self._max_retries = max_retries
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self) -> "EasiCoinClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def connect(self) -> None:
        if self._session is not None:
            return
        timeout = aiohttp.ClientTimeout(total=self._timeout)
        self._session = aiohttp.ClientSession(timeout=timeout)
        logger.info("API session created")

    async def close(self) -> None:
        if self._session is None:
            return
        await self._session.close()
        self._session = None
        logger.info("API session closed")

    def _build_query(self, params: Optional[dict[str, Any]]) -> str:
        if not params:
            return ""
        return urlencode(params, doseq=True)

    def _build_json_payload(self, data: Optional[dict[str, Any]]) -> str:
        if not data:
            return ""
        return json.dumps(data, separators=(",", ":"), ensure_ascii=True)

    def _sign(self, timestamp_ms: int, payload: str) -> str:
        message = f"{timestamp_ms}{self._api_key}{self._recv_window}{payload}"
        digest = hmac.new(
            self._api_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return digest

    def _auth_headers(self, timestamp_ms: int, payload: str) -> dict[str, str]:
        signature = self._sign(timestamp_ms, payload)
        return {
            "Access-Key": self._api_key,
            "Access-Sign": signature,
            "Access-Timestamp": str(timestamp_ms),
            "Recv-Window": str(self._recv_window),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _unwrap(self, resp_json: Any) -> Any:
        if isinstance(resp_json, dict) and "code" in resp_json:
            code = resp_json.get("code")
            if code not in (0, "0"):
                raise RuntimeError(f"API error code={code} msg={resp_json.get('message')}")
            if "data" in resp_json:
                return resp_json["data"]
        return resp_json

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
    ) -> Any:
        if self._session is None:
            raise RuntimeError("API session is not initialized")

        method_upper = method.upper()
        query = self._build_query(params) if method_upper in {"GET", "DELETE"} else ""
        payload = self._build_json_payload(data) if method_upper in {"POST", "PUT"} else query
        url = f"{self._base_url}/{path.lstrip('/')}"
        if query:
            url = f"{url}?{query}"

        for attempt in range(1, self._max_retries + 1):
            timestamp_ms = int(time.time() * 1000)
            headers = self._auth_headers(timestamp_ms, payload) if self._api_key else {
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            logger.info(
                "HTTP {method} {url} attempt={attempt}/{max_retries}",
                method=method_upper,
                url=url,
                attempt=attempt,
                max_retries=self._max_retries,
            )
            try:
                async with self._session.request(
                    method_upper,
                    url,
                    headers=headers,
                    json=data if method_upper in {"POST", "PUT"} else None,
                ) as resp:
                    if resp.status == 429:
                        retry_after = resp.headers.get("Retry-After")
                        wait_s = float(retry_after) if retry_after else min(2 ** attempt, 10)
                        logger.warning("Rate limited (429). Sleeping {wait_s:.2f}s", wait_s=wait_s)
                        await asyncio.sleep(wait_s)
                        continue

                    text_body = await resp.text()
                    if 200 <= resp.status < 300:
                        if "application/json" in resp.headers.get("Content-Type", ""):
                            parsed = json.loads(text_body) if text_body else {}
                            return self._unwrap(parsed)
                        return text_body

                    logger.error(
                        "HTTP error {status} body={body}",
                        status=resp.status,
                        body=text_body[:1000],
                    )
                    if attempt < self._max_retries and resp.status >= 500:
                        await asyncio.sleep(min(2 ** attempt, 10))
                        continue
                    resp.raise_for_status()
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                logger.error("Request failed: {error}", error=str(exc))
                if attempt >= self._max_retries:
                    raise
                await asyncio.sleep(min(2 ** attempt, 10))

        raise RuntimeError("Max retries exceeded")

    async def get(self, path: str, params: Optional[dict[str, Any]] = None) -> Any:
        return await self._request("GET", path, params=params)

    async def post(self, path: str, data: Optional[dict[str, Any]] = None) -> Any:
        return await self._request("POST", path, data=data)

    # ---------- Public Market ----------
    async def get_instruments(self, symbol: Optional[str] = None) -> Any:
        params = {"symbol": symbol} if symbol else None
        return await self.get("futures/public/v1/instruments", params=params)

    async def get_tickers(self, symbol: Optional[str] = None) -> Any:
        params = {"symbol": symbol} if symbol else None
        return await self.get("futures/public/v1/market/tickers", params=params)

    async def get_depth(self, symbol: str, depth: int = 20) -> Any:
        if not symbol:
            raise ValueError("symbol 不能为空")
        if depth <= 0 or depth > 25:
            raise ValueError("depth 必须在 1-25 之间")
        params = {"symbol": symbol, "depth": depth}
        return await self.get("futures/public/v1/market/order-book", params=params)

    async def get_kline(
        self,
        symbol: str,
        interval: str,
        start: Optional[int] = None,
        end: Optional[int] = None,
        limit: int = 100,
    ) -> Any:
        if not symbol:
            raise ValueError("symbol 不能为空")
        if not interval:
            raise ValueError("interval 不能为空")
        if limit <= 0 or limit > 100:
            raise ValueError("limit 必须在 1-100 之间")
        params: dict[str, Any] = {"symbol": symbol, "interval": interval, "limit": limit}
        if start is not None:
            params["start"] = start
        if end is not None:
            params["end"] = end
        return await self.get("futures/public/v1/market/kline", params=params)

    async def get_mark_price_kline(
        self,
        symbol: str,
        interval: str,
        start: Optional[int] = None,
        end: Optional[int] = None,
        limit: int = 100,
    ) -> Any:
        params: dict[str, Any] = {"symbol": symbol, "interval": interval, "limit": limit}
        if start is not None:
            params["start"] = start
        if end is not None:
            params["end"] = end
        return await self.get("futures/public/v1/market/mark-price-kline", params=params)

    async def get_trades(self, symbol: str, limit: int = 50) -> Any:
        if not symbol:
            raise ValueError("symbol 不能为空")
        if limit <= 0 or limit > 100:
            raise ValueError("limit 必须在 1-100 之间")
        params = {"symbol": symbol, "limit": limit}
        return await self.get("futures/public/v1/market/trades", params=params)

    async def get_funding_history(self, symbol: str, limit: int = 100, start: Optional[int] = None, end: Optional[int] = None) -> Any:
        params: dict[str, Any] = {"symbol": symbol, "limit": limit}
        if start is not None:
            params["from"] = start
        if end is not None:
            params["to"] = end
        return await self.get("futures/public/v1/market/funding-rate-history", params=params)

    # ---------- Account (private) ----------
    async def get_fee_rate(self, symbol: Optional[str] = None, coin: Optional[str] = None) -> Any:
        params: dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol
        if coin:
            params["coin"] = coin
        return await self.get("futures/private/v1/account/fee-rate", params=params or None)

    async def get_account_balance(self, coin: Optional[str] = None) -> Any:
        params = {"coin": coin} if coin else None
        return await self.get("futures/private/v1/account/balance", params=params)

    # ---------- Position (private) ----------
    async def get_positions(self, symbol: Optional[str] = None, coin: Optional[str] = None) -> Any:
        params: dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol
        if coin:
            params["coin"] = coin
        return await self.get("futures/private/v1/position/list", params=params or None)

    async def switch_position_mode(self, coin: str, position_mode: str) -> Any:
        return await self.post("futures/private/v1/position/switch-separate-mode", data={"coin": coin, "position_mode": position_mode})

    async def set_leverage(self, symbol: str, buy_leverage: Optional[int] = None, sell_leverage: Optional[int] = None, pz_link_id: Optional[str] = None) -> Any:
        payload: dict[str, Any] = {"symbol": symbol}
        if buy_leverage is not None:
            payload["buy_leverage"] = buy_leverage
        if sell_leverage is not None:
            payload["sell_leverage"] = sell_leverage
        if pz_link_id:
            payload["pz_link_id"] = pz_link_id
        return await self.post("futures/private/v1/position/set-leverage", data=payload)

    async def set_margin_mode(self, symbol: str, margin_mode: str) -> Any:
        return await self.post("futures/private/v1/position/switch-margin-mode", data={"symbol": symbol, "margin_mode": margin_mode})

    async def adjust_margin(self, symbol: str, position_idx: int, margin: str, pz_link_id: Optional[str] = None) -> Any:
        payload: dict[str, Any] = {"symbol": symbol, "position_idx": position_idx, "margin": margin}
        if pz_link_id:
            payload["pz_link_id"] = pz_link_id
        return await self.post("futures/private/v1/position/add-margin", data=payload)

    async def create_tpsl(self, payload: dict[str, Any]) -> Any:
        return await self.post("futures/private/v1/position/create-tpsl", data=payload)

    async def replace_tpsl(self, payload: dict[str, Any]) -> Any:
        return await self.post("futures/private/v1/position/replace-tpsl", data=payload)

    async def get_closed_pnl(self, symbol: Optional[str] = None, coin: Optional[str] = None, start: Optional[int] = None, end: Optional[int] = None, limit: int = 100, cursor: Optional[str] = None) -> Any:
        params: dict[str, Any] = {"limit": limit}
        if symbol:
            params["symbol"] = symbol
        if coin:
            params["coin"] = coin
        if start:
            params["start_time"] = start
        if end:
            params["end_time"] = end
        if cursor:
            params["cursor"] = cursor
        return await self.get("futures/private/v1/position/closed-pnl", params=params)

    # ---------- Order (private) ----------
    async def create_order(self, payload: dict[str, Any]) -> Any:
        return await self.post("futures/private/v1/create-order", data=payload)

    async def replace_order(self, payload: dict[str, Any]) -> Any:
        return await self.post("futures/private/v1/replace-order", data=payload)

    async def cancel_order(self, payload: dict[str, Any]) -> Any:
        return await self.post("futures/private/v1/cancel-order", data=payload)

    async def cancel_all_orders(self, payload: dict[str, Any]) -> Any:
        return await self.post("futures/private/v1/cancel-all-orders", data=payload)

    async def get_activity_orders(self, params: Optional[dict[str, Any]] = None) -> Any:
        return await self.get("futures/private/v1/trade/activity-orders", params=params)

    async def get_orders(self, params: Optional[dict[str, Any]] = None) -> Any:
        return await self.get("futures/private/v1/trade/orders", params=params)

    async def get_fills(self, params: Optional[dict[str, Any]] = None) -> Any:
        return await self.get("futures/private/v1/trade/fills", params=params)

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
            headers = self._auth_headers(timestamp_ms, payload)
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
                            return json.loads(text_body) if text_body else {}
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

    async def put(self, path: str, data: Optional[dict[str, Any]] = None) -> Any:
        return await self._request("PUT", path, data=data)

    async def delete(self, path: str, params: Optional[dict[str, Any]] = None) -> Any:
        return await self._request("DELETE", path, params=params)

    async def get_server_time(self) -> Any:
        return await self.get("public/time")

    async def get_tickers(self) -> Any:
        return await self.get("market/tickers")

    async def get_depth(self, symbol: str, limit: int = 20) -> Any:
        return await self.get("market/depth", params={"symbol": symbol, "limit": limit})

    async def get_kline(
        self,
        symbol: str,
        interval: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> Any:
        params: dict[str, Any] = {"symbol": symbol, "interval": interval}
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        if limit is not None:
            params["limit"] = limit
        return await self.get("market/kline", params=params)

    async def get_account_balance(self) -> Any:
        return await self.get("account/balance")

    async def get_positions(self) -> Any:
        return await self.get("position/list")

    async def place_order(self, payload: dict[str, Any]) -> Any:
        return await self.post("order/place", data=payload)

    async def cancel_order(self, order_id: str) -> Any:
        return await self.post("order/cancel", data={"orderId": order_id})

    async def close_position(self, symbol: str) -> Any:
        return await self.post("position/close", data={"symbol": symbol})

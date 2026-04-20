from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List, Optional

import requests

from ..settings import Settings


class AlpacaPaperBroker:
    def __init__(self, settings: Settings, dry_run: bool = True):
        self.settings = settings
        self.dry_run = dry_run

    def _headers(self) -> Dict[str, str]:
        api_key = str(self.settings.alpaca_api_key or "").strip()
        secret_key = str(self.settings.alpaca_secret_key or "").strip()
        if not api_key or not secret_key:
            raise RuntimeError("ALPACA_API_KEY/ALPACA_SECRET_KEY missing; cannot call Alpaca API")
        return {
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": secret_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    @property
    def base_url(self) -> str:
        return self.settings.alpaca_paper_base_url.rstrip("/")

    def get_account(self) -> Dict[str, Any]:
        if self.dry_run:
            return {"id": "dry-run", "status": "ACTIVE", "cash": "100000"}
        response = requests.get(f"{self.base_url}/v2/account", headers=self._headers(), timeout=30)
        response.raise_for_status()
        return response.json()

    def submit_order(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.dry_run:
            return {
                "id": f"dry-{uuid.uuid4().hex[:12]}",
                "submitted_at": datetime.utcnow().isoformat(),
                "status": "accepted",
                "payload": payload,
            }
        response = requests.post(
            f"{self.base_url}/v2/orders",
            headers=self._headers(),
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def place_option_order(
        self,
        symbol: str,
        qty: int,
        side: str,
        position_intent: str = "buy_to_open",
        order_type: str = "market",
        time_in_force: str = "day",
        limit_price: Optional[float] = None,
        client_order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "symbol": symbol,
            "qty": str(qty),
            "side": side,
            "type": order_type,
            "time_in_force": time_in_force,
            "position_intent": position_intent,
        }
        if limit_price is not None:
            payload["limit_price"] = str(round(limit_price, 2))
        client_text = str(client_order_id or "").strip()
        if client_text:
            payload["client_order_id"] = client_text
        return self.submit_order(payload)

    def list_orders(self, status: str = "open", limit: int = 50) -> List[Dict[str, Any]]:
        if self.dry_run:
            return []
        response = requests.get(
            f"{self.base_url}/v2/orders",
            headers=self._headers(),
            params={"status": status, "limit": limit},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def get_order(self, order_id: str) -> Dict[str, Any]:
        order_id = str(order_id or "").strip()
        if not order_id:
            return {}
        if self.dry_run:
            return {"id": order_id, "status": "accepted"}
        response = requests.get(
            f"{self.base_url}/v2/orders/{order_id}",
            headers=self._headers(),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def list_positions(self) -> List[Dict[str, Any]]:
        if self.dry_run:
            return []
        response = requests.get(
            f"{self.base_url}/v2/positions",
            headers=self._headers(),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()


class AlpacaDataProvider:
    def __init__(self, settings: Settings, session: Optional[requests.Session] = None):
        self.settings = settings
        self._session = session or requests.Session()
        self._historical_option_quotes_supported: Optional[bool] = None
        self._historical_option_trades_supported: Optional[bool] = None

    def _resolve_stock_feed(self, feed: Optional[str]) -> Optional[str]:
        explicit = str(feed or "").strip().lower()
        if explicit:
            return explicit
        return self.settings.alpaca_stock_feed()

    def _resolve_option_feed(self, feed: Optional[str]) -> Optional[str]:
        explicit = str(feed or "").strip().lower()
        if explicit:
            return explicit
        return self.settings.alpaca_option_feed()

    def _headers(self) -> Dict[str, str]:
        api_key = str(self.settings.alpaca_api_key or "").strip()
        secret_key = str(self.settings.alpaca_secret_key or "").strip()
        if not api_key or not secret_key:
            raise RuntimeError("ALPACA_API_KEY/ALPACA_SECRET_KEY missing; cannot call Alpaca data API")
        return {
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": secret_key,
            "Accept": "application/json",
        }

    def _get(self, url: str, *, params: Dict[str, Any], timeout: int = 30) -> requests.Response:
        return self._session.get(
            url,
            headers=self._headers(),
            params=params,
            timeout=timeout,
        )

    @property
    def contracts_base_url(self) -> str:
        # Alpaca exposes options contracts under the trading API host.
        return self.settings.alpaca_paper_base_url.rstrip("/")

    @property
    def market_data_base_url(self) -> str:
        return self.settings.alpaca_data_base_url.rstrip("/")

    def fetch_news(
        self,
        *,
        ticker: str,
        published_after: datetime,
        published_before: datetime,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        page_token: Optional[str] = None
        ticker_text = str(ticker or "").strip().upper()
        if not ticker_text:
            return rows

        while True:
            params: Dict[str, Any] = {
                "symbols": ticker_text,
                "start": published_after.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end": published_before.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "limit": max(1, min(int(limit), 50)),
            }
            if page_token:
                params["page_token"] = page_token

            response = self._get(f"{self.market_data_base_url}/v1beta1/news", params=params, timeout=30)
            response.raise_for_status()
            payload = response.json()
            for item in payload.get("news") or []:
                published_dt = _parse_alpaca_datetime(item.get("created_at") or item.get("updated_at"))
                rows.append(
                    {
                        "headline": str(item.get("headline") or ""),
                        "published_utc": published_dt,
                        "source": str(item.get("source") or ""),
                        "summary": str(item.get("summary") or ""),
                        "article_url": str(item.get("url") or ""),
                    }
                )
            page_token = payload.get("next_page_token")
            if not page_token:
                break
        return rows

    def fetch_option_contracts(
        self,
        underlying_symbol: str,
        expiration_date_gte: Optional[str] = None,
        expiration_date_lte: Optional[str] = None,
        expiration_date: Optional[str] = None,
        as_of: Optional[str] = None,
        option_type: Optional[str] = None,
        status: str = "inactive",
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        page_token: Optional[str] = None
        include_as_of = bool(as_of)

        while True:
            params: Dict[str, Any] = {
                "underlying_symbols": underlying_symbol,
                "status": status,
                "limit": limit,
            }
            if as_of and include_as_of:
                params["as_of"] = as_of
            if expiration_date:
                params["expiration_date"] = expiration_date
            else:
                if expiration_date_gte:
                    params["expiration_date_gte"] = expiration_date_gte
                if expiration_date_lte:
                    params["expiration_date_lte"] = expiration_date_lte
            if option_type:
                params["type"] = option_type
            if page_token:
                params["page_token"] = page_token

            try:
                response = self._get(f"{self.contracts_base_url}/v2/options/contracts", params=params, timeout=30)
                response.raise_for_status()
            except requests.HTTPError as exc:
                # Some environments reject `as_of`; retry once without it.
                if include_as_of and (
                    _is_unexpected_query_parameter_error(exc, "as_of")
                    or _is_invalid_option_contract_as_of_request(exc)
                ):
                    include_as_of = False
                    page_token = None
                    rows = []
                    continue
                raise
            payload = response.json()

            batch = payload.get("option_contracts") or []
            rows.extend(batch)

            page_token = payload.get("next_page_token")
            if not page_token:
                break

        return rows

    def fetch_option_quotes(
        self,
        symbol: str,
        start: str,
        end: str,
        limit: int = 10000,
        feed: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if self._historical_option_quotes_supported is False:
            return []
        rows: List[Dict[str, Any]] = []
        page_token: Optional[str] = None
        selected_feed = self._resolve_option_feed(feed)
        include_feed = bool(selected_feed)

        while True:
            params: Dict[str, Any] = {
                "symbols": symbol,
                "start": start,
                "end": end,
                "limit": limit,
            }
            if selected_feed and include_feed:
                params["feed"] = selected_feed
            if page_token:
                params["page_token"] = page_token

            try:
                response = self._get(f"{self.market_data_base_url}/v1beta1/options/quotes", params=params, timeout=30)
                response.raise_for_status()
            except requests.HTTPError as exc:
                if _is_not_found_error(exc):
                    # Some environments/plans do not expose a historical options quotes endpoint.
                    self._historical_option_quotes_supported = False
                    return []
                # Some Alpaca options endpoints reject `feed`; retry once without it.
                if selected_feed and include_feed and _is_unexpected_query_parameter_error(exc, "feed"):
                    include_feed = False
                    page_token = None
                    rows = []
                    continue
                raise
            payload = response.json()
            self._historical_option_quotes_supported = True

            quotes_map = payload.get("quotes") or {}
            quotes = quotes_map.get(symbol) or []
            rows.extend(quotes)

            page_token = payload.get("next_page_token")
            if not page_token:
                break

        return rows

    def fetch_option_trades(
        self,
        symbol: str,
        start: str,
        end: Optional[str] = None,
        limit: int = 10000,
        sort: str = "asc",
    ) -> List[Dict[str, Any]]:
        if self._historical_option_trades_supported is False:
            return []
        rows: List[Dict[str, Any]] = []
        page_token: Optional[str] = None

        while True:
            params: Dict[str, Any] = {
                "symbols": symbol,
                "start": start,
                "limit": limit,
                "sort": sort,
            }
            if end:
                params["end"] = end
            if page_token:
                params["page_token"] = page_token

            try:
                response = self._get(f"{self.market_data_base_url}/v1beta1/options/trades", params=params, timeout=30)
                response.raise_for_status()
            except requests.HTTPError as exc:
                if _is_not_found_error(exc):
                    self._historical_option_trades_supported = False
                    return []
                raise
            payload = response.json()
            self._historical_option_trades_supported = True

            trades_map = payload.get("trades") or {}
            trades = trades_map.get(symbol) or []
            rows.extend(trades)

            page_token = payload.get("next_page_token")
            if not page_token:
                break

        return rows

    def fetch_option_bars(
        self,
        symbol: str,
        start: str,
        end: str,
        timeframe: str = "1Day",
        limit: int = 10000,
        feed: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        page_token: Optional[str] = None
        selected_feed = self._resolve_option_feed(feed)
        include_feed = bool(selected_feed)

        while True:
            params: Dict[str, Any] = {
                "symbols": symbol,
                "timeframe": timeframe,
                "start": start,
                "end": end,
                "limit": limit,
            }
            if selected_feed and include_feed:
                params["feed"] = selected_feed
            if page_token:
                params["page_token"] = page_token

            try:
                response = self._get(f"{self.market_data_base_url}/v1beta1/options/bars", params=params, timeout=30)
                response.raise_for_status()
            except requests.HTTPError as exc:
                # Some Alpaca options endpoints reject `feed`; retry once without it.
                if selected_feed and include_feed and _is_unexpected_query_parameter_error(exc, "feed"):
                    include_feed = False
                    page_token = None
                    rows = []
                    continue
                raise
            payload = response.json()

            bars_map = payload.get("bars") or {}
            bars = bars_map.get(symbol) or []
            rows.extend(bars)

            page_token = payload.get("next_page_token")
            if not page_token:
                break

        return rows

    def fetch_latest_option_quote(self, symbol: str, feed: Optional[str] = None) -> Optional[Dict[str, Any]]:
        symbol_text = str(symbol or "").strip()
        if not symbol_text:
            return None
        params: Dict[str, Any] = {"symbols": symbol_text}
        selected_feed = self._resolve_option_feed(feed)
        include_feed = bool(selected_feed)
        if selected_feed and include_feed:
            params["feed"] = selected_feed
        try:
            response = self._get(f"{self.market_data_base_url}/v1beta1/options/quotes/latest", params=params, timeout=30)
            response.raise_for_status()
        except requests.HTTPError as exc:
            if selected_feed and include_feed and _is_unexpected_query_parameter_error(exc, "feed"):
                response = self._get(
                    f"{self.market_data_base_url}/v1beta1/options/quotes/latest",
                    params={"symbols": symbol_text},
                    timeout=30,
                )
                response.raise_for_status()
            else:
                raise
        payload = response.json()
        quotes_map = payload.get("quotes") or {}
        row = quotes_map.get(symbol_text)
        if not isinstance(row, dict):
            return None
        bid = row.get("bp", row.get("bid_price"))
        ask = row.get("ap", row.get("ask_price"))
        return {
            "bid": float(bid) if bid is not None else None,
            "ask": float(ask) if ask is not None else None,
            "ts": row.get("t"),
        }

    def fetch_stock_bars(
        self,
        symbol: str,
        start: str,
        end: str,
        timeframe: str = "1Day",
        limit: int = 10000,
        feed: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        page_token: Optional[str] = None
        selected_feed = self._resolve_stock_feed(feed)

        while True:
            params: Dict[str, Any] = {
                "timeframe": timeframe,
                "start": start,
                "end": end,
                "limit": limit,
                "adjustment": "all",
            }
            if selected_feed:
                params["feed"] = selected_feed
            if page_token:
                params["page_token"] = page_token

            try:
                response = self._get(f"{self.market_data_base_url}/v2/stocks/{symbol}/bars", params=params, timeout=30)
                response.raise_for_status()
            except requests.HTTPError as exc:
                # Some accounts cannot access recent SIP data. Retry once with IEX.
                if selected_feed in {None, "sip"} and _is_recent_sip_permission_error(exc):
                    selected_feed = "iex"
                    page_token = None
                    rows = []
                    continue
                raise
            payload = response.json()
            rows.extend(payload.get("bars") or [])
            page_token = payload.get("next_page_token")
            if not page_token:
                break

        return rows


def _is_recent_sip_permission_error(exc: requests.HTTPError) -> bool:
    response = getattr(exc, "response", None)
    if response is None or int(getattr(response, "status_code", 0)) != 403:
        return False
    message = ""
    try:
        payload = response.json()
    except Exception:
        payload = {}
    if isinstance(payload, dict):
        message = str(payload.get("message") or "")
    if not message:
        message = str(getattr(response, "text", "") or "")
    normalized = message.lower()
    return "subscription does not permit" in normalized and "sip" in normalized


def _is_unexpected_query_parameter_error(exc: requests.HTTPError, parameter: str) -> bool:
    response = getattr(exc, "response", None)
    if response is None or int(getattr(response, "status_code", 0)) != 400:
        return False
    message = ""
    try:
        payload = response.json() or {}
    except Exception:
        payload = {}
    if isinstance(payload, dict):
        message = str(payload.get("message") or "")
    if not message:
        message = str(getattr(response, "text", "") or "")
    normalized = message.lower()
    parameter_text = str(parameter or "").strip().lower()
    return "unexpected query parameter" in normalized and parameter_text in normalized


def _is_not_found_error(exc: requests.HTTPError) -> bool:
    response = getattr(exc, "response", None)
    if response is None:
        return False
    return int(getattr(response, "status_code", 0)) == 404


def _is_invalid_option_contract_as_of_request(exc: requests.HTTPError) -> bool:
    response = getattr(exc, "response", None)
    if response is None or int(getattr(response, "status_code", 0)) != 422:
        return False
    message = ""
    try:
        payload = response.json() or {}
    except Exception:
        payload = {}
    if isinstance(payload, dict):
        message = str(payload.get("message") or "")
    if not message:
        message = str(getattr(response, "text", "") or "")
    normalized = message.lower()
    return "request parameters are invalid" in normalized


def _parse_alpaca_datetime(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)

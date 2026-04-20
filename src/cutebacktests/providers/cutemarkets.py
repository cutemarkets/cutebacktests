from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import threading
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests

from ..settings import Settings
from ..utils import parse_datetime


_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_REQUEST_ATTEMPTS = 4
_BASE_RETRY_DELAY_SECONDS = 0.75


class CuteMarketsProvider:
    def __init__(self, settings: Settings, session: Optional[requests.Session] = None):
        self.settings = settings
        self._session = session or requests.Session()
        self._stats_lock = threading.Lock()
        self._stats: Dict[str, Any] = {
            "request_count": 0,
            "response_bytes": 0,
            "network_seconds": 0.0,
            "decode_seconds": 0.0,
            "result_rows": 0,
            "category_counts": {},
            "category_response_bytes": {},
            "category_network_seconds": {},
            "category_decode_seconds": {},
            "category_result_rows": {},
            "option_quote_fetch_calls": 0,
            "option_quote_fetch_pages": 0,
            "option_quote_probe_calls": 0,
        }

    def _record_request_stats(
        self,
        *,
        category: str,
        response_bytes: int,
        network_seconds: float,
        decode_seconds: float,
        result_rows: int,
    ) -> None:
        with self._stats_lock:
            self._stats["request_count"] = int(self._stats.get("request_count") or 0) + 1
            self._stats["response_bytes"] = int(self._stats.get("response_bytes") or 0) + int(response_bytes or 0)
            self._stats["network_seconds"] = float(self._stats.get("network_seconds") or 0.0) + float(
                network_seconds or 0.0
            )
            self._stats["decode_seconds"] = float(self._stats.get("decode_seconds") or 0.0) + float(
                decode_seconds or 0.0
            )
            self._stats["result_rows"] = int(self._stats.get("result_rows") or 0) + int(result_rows or 0)
            for field, value in (
                ("category_counts", 1),
                ("category_response_bytes", int(response_bytes or 0)),
                ("category_network_seconds", float(network_seconds or 0.0)),
                ("category_decode_seconds", float(decode_seconds or 0.0)),
                ("category_result_rows", int(result_rows or 0)),
            ):
                bucket = dict(self._stats.get(field) or {})
                bucket[category] = float(bucket.get(category) or 0.0) + float(value)
                self._stats[field] = bucket

    def _bump_stat(self, key: str, amount: int = 1) -> None:
        with self._stats_lock:
            self._stats[key] = int(self._stats.get(key) or 0) + int(amount)

    def take_stats(self, *, reset: bool = False) -> Dict[str, Any]:
        with self._stats_lock:
            payload = {
                "request_count": int(self._stats.get("request_count") or 0),
                "response_bytes": int(self._stats.get("response_bytes") or 0),
                "network_seconds": float(self._stats.get("network_seconds") or 0.0),
                "decode_seconds": float(self._stats.get("decode_seconds") or 0.0),
                "result_rows": int(self._stats.get("result_rows") or 0),
                "option_quote_fetch_calls": int(self._stats.get("option_quote_fetch_calls") or 0),
                "option_quote_fetch_pages": int(self._stats.get("option_quote_fetch_pages") or 0),
                "option_quote_probe_calls": int(self._stats.get("option_quote_probe_calls") or 0),
                "category_counts": {
                    key: int(value)
                    for key, value in dict(self._stats.get("category_counts") or {}).items()
                },
                "category_response_bytes": {
                    key: int(value)
                    for key, value in dict(self._stats.get("category_response_bytes") or {}).items()
                },
                "category_network_seconds": {
                    key: float(value)
                    for key, value in dict(self._stats.get("category_network_seconds") or {}).items()
                },
                "category_decode_seconds": {
                    key: float(value)
                    for key, value in dict(self._stats.get("category_decode_seconds") or {}).items()
                },
                "category_result_rows": {
                    key: int(value)
                    for key, value in dict(self._stats.get("category_result_rows") or {}).items()
                },
            }
            if reset:
                self._stats = {
                    "request_count": 0,
                    "response_bytes": 0,
                    "network_seconds": 0.0,
                    "decode_seconds": 0.0,
                    "result_rows": 0,
                    "category_counts": {},
                    "category_response_bytes": {},
                    "category_network_seconds": {},
                    "category_decode_seconds": {},
                    "category_result_rows": {},
                    "option_quote_fetch_calls": 0,
                    "option_quote_fetch_pages": 0,
                    "option_quote_probe_calls": 0,
                }
        return payload

    def _request_category(self, target: str) -> str:
        value = str(target or "")
        if "/v3/quotes/" in value:
            return "option_quotes"
        if "/v3/snapshot/options/" in value:
            return "option_chain_snapshot"
        if "/v3/reference/options/contracts" in value:
            return "option_contracts"
        if "/v2/aggs/ticker/" in value and ("%3A" in value or "/O:" in value):
            return "option_bars"
        if "/v2/aggs/ticker/" in value:
            return "stock_bars"
        if "/v2/reference/news" in value:
            return "news"
        return "other"

    @staticmethod
    def _response_text_snippet(response: requests.Response) -> str:
        text = str(getattr(response, "text", "") or "").strip()
        if not text:
            return ""
        text = " ".join(text.split())
        if len(text) > 200:
            return text[:197] + "..."
        return text

    @staticmethod
    def _retry_delay_seconds(attempt: int) -> float:
        normalized_attempt = max(int(attempt), 1)
        return _BASE_RETRY_DELAY_SECONDS * float(normalized_attempt)

    def _request_json(
        self,
        *,
        target: str,
        url: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        category = self._request_category(target)
        safe_params = {key: value for key, value in dict(params or {}).items() if key != "apiKey"}
        last_status_code: Optional[int] = None
        last_body = ""
        last_error: Optional[Exception] = None
        for attempt in range(1, _MAX_REQUEST_ATTEMPTS + 1):
            network_started_at = time.perf_counter()
            try:
                response = self._session.get(url, params=params, timeout=30)
            except requests.RequestException as exc:
                last_error = exc
                if attempt < _MAX_REQUEST_ATTEMPTS:
                    time.sleep(self._retry_delay_seconds(attempt))
                    continue
                break
            network_elapsed = max(time.perf_counter() - network_started_at, 0.0)
            raw_status_code = getattr(response, "status_code", 200)
            try:
                status_code = int(raw_status_code)
            except Exception:
                status_code = 200
            last_status_code = status_code
            last_body = self._response_text_snippet(response)
            if status_code in _RETRYABLE_STATUS_CODES and attempt < _MAX_REQUEST_ATTEMPTS:
                time.sleep(self._retry_delay_seconds(attempt))
                continue
            try:
                response.raise_for_status()
            except requests.HTTPError as exc:
                last_error = exc
                break
            raw_bytes = len(response.content or b"")
            decode_started_at = time.perf_counter()
            payload = response.json()
            decode_elapsed = max(time.perf_counter() - decode_started_at, 0.0)
            self._record_request_stats(
                category=category,
                response_bytes=raw_bytes,
                network_seconds=network_elapsed,
                decode_seconds=decode_elapsed,
                result_rows=len(payload.get("results", []) or []) if isinstance(payload, dict) else 0,
            )
            return payload
        error_parts = ["CuteMarkets request failed"]
        if last_status_code is not None:
            error_parts.append(f"status={last_status_code}")
        error_parts.append(f"category={category}")
        error_parts.append(f"url={url}")
        if safe_params:
            error_parts.append(f"params={safe_params}")
        if last_body:
            error_parts.append(f"body={last_body}")
        if last_error is not None:
            error_parts.append(f"error={type(last_error).__name__}: {last_error}")
        raise RuntimeError(" ".join(str(part) for part in error_parts))

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        api_key = str(self.settings.cutemarkets_api_key or "").strip()
        if not api_key:
            raise RuntimeError("CUTEMARKETS_API_KEY is missing; cannot call CuteMarkets API")
        full_params = dict(params or {})
        full_params["apiKey"] = api_key
        url = self.settings.cutemarkets_base_url.rstrip("/") + path
        return self._request_json(target=path, url=url, params=full_params)

    def _get_next(self, next_url: str) -> Dict[str, Any]:
        api_key = str(self.settings.cutemarkets_api_key or "").strip()
        if not api_key:
            raise RuntimeError("CUTEMARKETS_API_KEY is missing; cannot call CuteMarkets API")
        return self._request_json(target=next_url, url=next_url, params={"apiKey": api_key})

    def fetch_stock_bars(
        self,
        ticker: str,
        start: date,
        end: date,
        multiplier: int = 1,
        timespan: str = "day",
    ) -> List[Dict[str, Any]]:
        path = f"/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{start}/{end}"
        rows: List[Dict[str, Any]] = []
        next_url: Optional[str] = None
        while True:
            if next_url:
                data = self._get_next(next_url)
            else:
                data = self._get(path, params={"adjusted": "true", "limit": 50000, "sort": "asc"})
            for item in data.get("results", []):
                rows.append(
                    {
                        "ticker": ticker,
                        "ts": datetime.utcfromtimestamp(item["t"] / 1000.0),
                        "open": float(item.get("o", 0.0)),
                        "high": float(item.get("h", 0.0)),
                        "low": float(item.get("l", 0.0)),
                        "close": float(item.get("c", 0.0)),
                        "volume": int(item.get("v", 0)),
                    }
                )
            next_url = data.get("next_url")
            if not next_url:
                break
        return rows

    def fetch_option_chain_snapshot(
        self,
        underlying: str,
        as_of: Optional[date] = None,
        limit: int = 250,
        paginate: bool = True,
        max_pages: Optional[int] = None,
        expiration_date: Optional[str] = None,
        expiration_date_gte: Optional[str] = None,
        expiration_date_lte: Optional[str] = None,
        contract_type: Optional[str] = None,
        strike_price: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        if as_of is not None:
            params["as_of"] = str(as_of)
        if expiration_date:
            params["expiration_date"] = str(expiration_date)
        else:
            if expiration_date_gte:
                params["expiration_date.gte"] = str(expiration_date_gte)
            if expiration_date_lte:
                params["expiration_date.lte"] = str(expiration_date_lte)
        if contract_type:
            params["contract_type"] = str(contract_type)
        if strike_price is not None:
            params["strike_price"] = float(strike_price)

        # This snapshot route rejects `limit` on some provider-compatible deployments.
        # Keep the argument for call-site compatibility, but never forward it.
        path = f"/v3/snapshot/options/{underlying}"
        # Stamp one snapshot time for the whole fetch so downstream reads get a coherent chain.
        snapshot_ts = datetime.utcnow()
        rows: List[Dict[str, Any]] = []
        next_url: Optional[str] = None
        pages_fetched = 0
        while True:
            data = self._get_next(next_url) if next_url else self._get(path, params=params)
            pages_fetched += 1
            for item in data.get("results", []):
                details = item.get("details", {}) or {}
                greeks = item.get("greeks", {}) or {}
                quote_data = item.get("last_quote", {}) or item.get("quote", {}) or {}
                day_data = item.get("day", {}) or {}

                rows.append(
                    {
                        "option_symbol": details.get("ticker") or item.get("ticker") or "",
                        "underlying": details.get("underlying_ticker") or underlying,
                        "ts": snapshot_ts,
                        "expiration": parse_datetime(details.get("expiration_date")),
                        "strike": float(details.get("strike_price", 0.0)),
                        "option_type": str(details.get("contract_type", "")).lower(),
                        "bid": float(
                            _safe_float(quote_data.get("bid_price", quote_data.get("bid"))) or 0.0
                        ),
                        "ask": float(
                            _safe_float(quote_data.get("ask_price", quote_data.get("ask"))) or 0.0
                        ),
                        "midpoint": _safe_float(quote_data.get("midpoint", quote_data.get("mid"))),
                        "delta": _safe_float(greeks.get("delta")),
                        "iv": _safe_float(item.get("implied_volatility")),
                        "open_interest": int(item.get("open_interest") or 0),
                        "volume": int(day_data.get("volume") or 0),
                    }
                )
            next_url = data.get("next_url")
            if not paginate or not next_url:
                break
            if max_pages is not None and pages_fetched >= int(max_pages):
                break
        return [row for row in rows if row["option_symbol"]]

    def fetch_option_contract_snapshot(
        self,
        underlying: str,
        option_symbol: str,
        *,
        as_of: Optional[date] = None,
    ) -> Optional[Dict[str, Any]]:
        encoded_symbol = quote(str(option_symbol).strip(), safe="")
        path = f"/v3/snapshot/options/{underlying}/{encoded_symbol}"
        params: Dict[str, Any] = {}
        if as_of is not None:
            params["as_of"] = str(as_of)

        data = self._get(path, params=params)
        item = data.get("results") or {}
        if not isinstance(item, dict) or not item:
            return None

        details = item.get("details", {}) or {}
        greeks = item.get("greeks", {}) or {}
        quote_data = item.get("last_quote", {}) or item.get("quote", {}) or {}
        day_data = item.get("day", {}) or {}
        mapped_symbol = details.get("ticker") or item.get("ticker") or str(option_symbol).strip()
        if not mapped_symbol:
            return None
        return {
            "option_symbol": mapped_symbol,
            "underlying": details.get("underlying_ticker") or underlying,
            "ts": datetime.utcnow(),
            "expiration": parse_datetime(details.get("expiration_date")),
            "strike": float(details.get("strike_price", 0.0)),
            "option_type": str(details.get("contract_type", "")).lower(),
            "bid": float(_safe_float(quote_data.get("bid_price", quote_data.get("bid"))) or 0.0),
            "ask": float(_safe_float(quote_data.get("ask_price", quote_data.get("ask"))) or 0.0),
            "midpoint": _safe_float(quote_data.get("midpoint", quote_data.get("mid"))),
            "delta": _safe_float(greeks.get("delta")),
            "iv": _safe_float(item.get("implied_volatility")),
            "open_interest": int(item.get("open_interest") or 0),
            "volume": int(day_data.get("volume") or 0),
        }

    def fetch_option_contracts(
        self,
        underlying: Optional[str] = None,
        *,
        underlying_symbol: Optional[str] = None,
        limit: int = 250,
        paginate: bool = True,
        max_pages: Optional[int] = None,
        expired: Optional[bool] = None,
        expiration_date: Optional[str] = None,
        expiration_date_gte: Optional[str] = None,
        expiration_date_lte: Optional[str] = None,
        contract_type: Optional[str] = None,
        option_type: Optional[str] = None,
        strike_price: Optional[float] = None,
        as_of: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        resolved_underlying = str(underlying_symbol or underlying or "").strip().upper()
        if not resolved_underlying:
            return []
        if status is not None and expired is None:
            expired = str(status or "").strip().lower() != "active"
        resolved_limit = max(1, min(int(limit or 250), 1000))
        resolved_contract_type = str(option_type or contract_type or "").strip().lower()
        params: Dict[str, Any] = {
            "underlying_ticker": resolved_underlying,
            "limit": resolved_limit,
        }
        if expired is not None:
            params["expired"] = "true" if bool(expired) else "false"
        if as_of and params.get("expired") == "false":
            params["as_of"] = str(as_of)
        if expiration_date:
            params["expiration_date"] = str(expiration_date)
        else:
            if expiration_date_gte:
                params["expiration_date.gte"] = str(expiration_date_gte)
            if expiration_date_lte:
                params["expiration_date.lte"] = str(expiration_date_lte)
        if resolved_contract_type:
            params["contract_type"] = resolved_contract_type
        if strike_price is not None:
            params["strike_price"] = float(strike_price)

        path = "/v3/reference/options/contracts"
        rows: List[Dict[str, Any]] = []
        next_url: Optional[str] = None
        pages_fetched = 0
        while True:
            data = self._get_next(next_url) if next_url else self._get(path, params=params)
            pages_fetched += 1
            for item in data.get("results", []):
                ticker = str(item.get("ticker") or "").strip()
                strike = _safe_float(item.get("strike_price"))
                option_kind = str(item.get("contract_type") or item.get("type") or "").strip().lower()
                if not ticker or strike is None:
                    continue
                mapped_underlying = str(item.get("underlying_ticker") or resolved_underlying).strip().upper()
                expiration_text = str(item.get("expiration_date") or "").strip()
                rows.append(
                    {
                        "option_symbol": ticker,
                        "underlying": mapped_underlying,
                        "expiration": parse_datetime(expiration_text),
                        "strike": float(strike),
                        "option_type": option_kind,
                        "exercise_style": item.get("exercise_style"),
                        "shares_per_contract": item.get("shares_per_contract"),
                        "primary_exchange": item.get("primary_exchange"),
                        "symbol": ticker,
                        "underlying_symbol": mapped_underlying,
                        "expiration_date": expiration_text,
                        "strike_price": float(strike),
                        "type": option_kind,
                        "status": (
                            "active"
                            if params.get("expired") == "false"
                            else "inactive" if params.get("expired") == "true" else ""
                        ),
                        "style": str(item.get("exercise_style") or "").strip().lower(),
                        "open_interest": int(item.get("open_interest") or 0),
                        "volume": int(item.get("volume") or 0),
                        "delta": _safe_float(
                            ((item.get("greeks") or {}) if isinstance(item.get("greeks"), dict) else {}).get("delta")
                        ),
                    }
                )
            next_url = data.get("next_url")
            if not paginate or not next_url:
                break
            if max_pages is not None and pages_fetched >= int(max_pages):
                break
        return [row for row in rows if row["option_symbol"]]

    def fetch_option_bars(
        self,
        option_symbol: str,
        start: date,
        end: date,
        multiplier: int = 1,
        timespan: str = "day",
    ) -> List[Dict[str, Any]]:
        last_error: Optional[Exception] = None
        for candidate in _option_symbol_candidates(option_symbol):
            encoded = quote(candidate, safe="")
            path = f"/v2/aggs/ticker/{encoded}/range/{multiplier}/{timespan}/{start}/{end}"
            try:
                data = self._get(path, params={"adjusted": "true", "limit": 50000, "sort": "asc"})
            except Exception as exc:
                last_error = exc
                continue
            rows = []
            for item in data.get("results", []):
                rows.append(
                    {
                        "symbol": option_symbol,
                        "ts": datetime.utcfromtimestamp(item["t"] / 1000.0),
                        "open": float(item.get("o", 0.0)),
                        "high": float(item.get("h", 0.0)),
                        "low": float(item.get("l", 0.0)),
                        "close": float(item.get("c", 0.0)),
                        "volume": int(item.get("v", 0)),
                    }
                )
            if rows:
                return rows
        if last_error is not None:
            raise last_error
        return []

    def fetch_ticker_details(self, ticker: str) -> Dict[str, Any]:
        """Return reference data for *ticker* from the provider's /v3/reference/tickers route.

        Returned keys (all may be None if the provider omits them):
          shares_outstanding  – total shares outstanding (int)
          float_shares        – weighted/float shares outstanding (int)
          primary_exchange    – MIC code, e.g. "XNAS", "XNYS"
          market_cap          – float, USD

        Note: shares_outstanding reflects the *current* value.  For historical
        backtests, callers should apply estimate_historical_float() from
        strategy/lfcm.py to adjust for share-count drift over time.
        """
        path = f"/v3/reference/tickers/{ticker.upper().strip()}"
        data = self._get(path)
        result = data.get("results") or {}
        shares_outstanding = result.get("share_class_shares_outstanding") or result.get("shares_outstanding")
        float_shares = result.get("weighted_shares_outstanding")
        return {
            "ticker": ticker,
            "shares_outstanding": int(shares_outstanding) if shares_outstanding is not None else None,
            "float_shares": int(float_shares) if float_shares is not None else None,
            "primary_exchange": result.get("primary_exchange"),
            "market_cap": _safe_float(result.get("market_cap")),
        }

    def fetch_news(
        self,
        ticker: str,
        published_after: datetime,
        published_before: datetime,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Fetch news articles for *ticker* published within the given UTC window.

        Returned list is sorted ascending by published_utc.  Each element has:
          headline       – str
          published_utc  – datetime (naive UTC)
          publisher      – str
          article_url    – str
        """
        path = "/v2/reference/news"
        params: Dict[str, Any] = {
            "ticker": ticker.upper().strip(),
            "published_utc.gte": published_after.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "published_utc.lte": published_before.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "order": "asc",
            "sort": "published_utc",
            "limit": max(1, min(int(limit), 1000)),
        }
        rows: List[Dict[str, Any]] = []
        next_url: Optional[str] = None
        while True:
            data = self._get_next(next_url) if next_url else self._get(path, params=params)
            for item in data.get("results", []) or []:
                published_raw = item.get("published_utc") or ""
                try:
                    published_dt = datetime.strptime(published_raw[:19], "%Y-%m-%dT%H:%M:%S")
                except (ValueError, TypeError):
                    published_dt = None
                publisher_obj = item.get("publisher") or {}
                publisher = (
                    publisher_obj.get("name", "")
                    if isinstance(publisher_obj, dict)
                    else str(publisher_obj)
                )
                rows.append(
                    {
                        "headline": str(item.get("title") or ""),
                        "published_utc": published_dt,
                        "publisher": publisher,
                        "article_url": str(item.get("article_url") or ""),
                    }
                )
            next_url = data.get("next_url")
            if not next_url:
                break
        return rows

    def fetch_option_quotes(
        self,
        option_symbol: str,
        start: datetime,
        end: datetime,
        limit: Optional[int] = 50000,
    ) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        requested_limit = None if limit is None else int(limit)
        limit_value = None if requested_limit is None or requested_limit <= 0 else max(1, int(requested_limit))
        sort_order = "asc"
        start_ns = _datetime_to_ns(start)
        end_ns = _datetime_to_ns(end)
        self._bump_stat("option_quote_fetch_calls")

        last_error: Optional[Exception] = None
        for candidate in _option_symbol_candidates(option_symbol):
            path = f"/v3/quotes/{quote(candidate, safe='')}"
            params: Dict[str, Any] = {
                "timestamp.gte": start_ns,
                "timestamp.lt": end_ns,
                "order": sort_order,
                "sort": "timestamp",
                "limit": 50000 if limit_value is None else min(limit_value, 50000),
            }
            next_url: Optional[str] = None
            try:
                while True:
                    if next_url:
                        payload = self._get_next(next_url)
                    else:
                        payload = self._get(path, params=params)
                    self._bump_stat("option_quote_fetch_pages")
                    mapped = _map_option_quote_results(
                        option_symbol=option_symbol,
                        raw_rows=payload.get("results", []) or [],
                        start=start,
                        end=end,
                    )
                    if mapped:
                        if limit_value is None:
                            rows.extend(mapped)
                        else:
                            remaining = max(int(limit_value) - len(rows), 0)
                            if remaining > 0:
                                rows.extend(mapped[:remaining])
                    if limit_value is not None and len(rows) >= limit_value:
                        break
                    next_url = payload.get("next_url")
                    if not next_url:
                        break
            except Exception as exc:
                last_error = exc
                continue
            if rows:
                break

        if not rows and last_error is not None:
            raise last_error
        rows.sort(key=lambda item: item["ts"])
        return rows

    def fetch_option_quote_probe(
        self,
        *,
        option_symbol: str,
        ts: datetime,
        day: date,
        fallback_last: bool = False,
    ) -> Optional[Dict[str, Any]]:
        self._bump_stat("option_quote_probe_calls")
        day_start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
        day_end = datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        selection_ts = ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)
        selection_ts = selection_ts.astimezone(timezone.utc)

        first_after = self.fetch_option_quotes(
            option_symbol=option_symbol,
            start=max(selection_ts, day_start),
            end=day_end,
            limit=1,
        )
        if first_after:
            return dict(first_after[0])
        if not fallback_last:
            return None
        last_before = self._fetch_option_quotes_desc(
            option_symbol=option_symbol,
            start=day_start,
            end=min(selection_ts, day_end),
            limit=1,
        )
        if last_before:
            return dict(last_before[0])
        return None

    def _fetch_option_quotes_desc(
        self,
        *,
        option_symbol: str,
        start: datetime,
        end: datetime,
        limit: int = 1,
    ) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        limit_value = max(1, min(int(limit), 50000))
        start_ns = _datetime_to_ns(start)
        end_ns = _datetime_to_ns(end)

        last_error: Optional[Exception] = None
        for candidate in _option_symbol_candidates(option_symbol):
            path = f"/v3/quotes/{quote(candidate, safe='')}"
            params: Dict[str, Any] = {
                "timestamp.gte": start_ns,
                "timestamp.lt": end_ns,
                "order": "desc",
                "sort": "timestamp",
                "limit": limit_value,
            }
            try:
                payload = self._get(path, params=params)
            except Exception as exc:
                last_error = exc
                continue
            mapped = _map_option_quote_results(
                option_symbol=option_symbol,
                raw_rows=payload.get("results", []) or [],
                start=start,
                end=end,
            )
            if mapped:
                rows.extend(mapped)
                break
        if not rows and last_error is not None:
            raise last_error
        rows.sort(key=lambda item: item["ts"])
        return rows


def _map_option_quote_results(
    *,
    option_symbol: str,
    raw_rows: List[Dict[str, Any]],
    start: datetime,
    end: datetime,
) -> List[Dict[str, Any]]:
    mapped: List[Dict[str, Any]] = []
    for item in raw_rows:
        ts = _quote_timestamp_to_datetime(item)
        if ts is None:
            continue
        if ts < _as_utc_naive(start) or ts >= _as_utc_naive(end):
            continue
        bid = _safe_float(item.get("bid_price", item.get("bp")))
        ask = _safe_float(item.get("ask_price", item.get("ap")))
        bid_size = int(item.get("bid_size", item.get("bs")) or 0)
        ask_size = int(item.get("ask_size", item.get("as")) or 0)
        if bid is None or ask is None:
            continue
        mapped.append(
            {
                "symbol": option_symbol,
                "ts": ts,
                "bid": bid,
                "ask": ask,
                "bid_size": bid_size,
                "ask_size": ask_size,
            }
        )
    return mapped


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _datetime_to_ns(value: datetime) -> int:
    if value.tzinfo is None:
        aware = value.replace(tzinfo=timezone.utc)
    else:
        aware = value.astimezone(timezone.utc)
    return int(aware.timestamp() * 1_000_000_000)


def _as_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _quote_timestamp_to_datetime(row: Dict[str, Any]) -> Optional[datetime]:
    for key in ("sip_timestamp", "participant_timestamp", "trf_timestamp", "timestamp"):
        raw = row.get(key)
        if raw is None:
            continue
        try:
            if isinstance(raw, str) and raw.strip().isdigit():
                raw = int(raw)
            if isinstance(raw, (int, float)):
                return datetime.utcfromtimestamp(float(raw) / 1_000_000_000.0)
        except Exception:
            continue
    return parse_datetime(row.get("t"))


def _option_symbol_candidates(option_symbol: str) -> List[str]:
    clean = str(option_symbol or "").strip().upper()
    if not clean:
        return []
    if clean.startswith("O:"):
        return [clean, clean[2:]]
    return [f"O:{clean}", clean]

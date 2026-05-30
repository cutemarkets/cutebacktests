from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from urllib.parse import quote

import requests

from ..settings import Settings


class CuteMarketsPaperBroker:
    """Small adapter for the CuteMarkets `/v1/paper` API.

    This is intentionally an API wrapper, not a live trading bot. The caller owns
    scheduling, signal generation, risk controls, and reconciliation.
    """

    def __init__(self, settings: Settings, session: Optional[requests.Session] = None, timeout: int = 30):
        self.settings = settings
        self._session = session or requests.Session()
        self.timeout = int(timeout)

    @property
    def base_url(self) -> str:
        return self.settings.cutemarkets_base_url.rstrip("/")

    def _api_key(self) -> str:
        api_key = str(self.settings.cutemarkets_paper_api_key or self.settings.cutemarkets_api_key or "").strip()
        if not api_key:
            raise RuntimeError("CUTEMARKETS_PAPER_API_KEY or CUTEMARKETS_API_KEY is missing; cannot call CuteMarkets paper API")
        return api_key

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key()}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        request_method = getattr(self._session, method.lower())
        kwargs: Dict[str, Any] = {
            "headers": self._headers(),
            "params": params or None,
            "timeout": self.timeout,
        }
        if body is not None:
            kwargs["json"] = body
        response = request_method(url, **kwargs)
        response.raise_for_status()
        if getattr(response, "status_code", None) == 204:
            return {}
        if not str(getattr(response, "text", "") or "").strip():
            return {}
        return response.json()

    @staticmethod
    def _results(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        rows = payload.get("results", [])
        return rows if isinstance(rows, list) else []

    def list_accounts(self, *, include_archived: bool = False, limit: int = 100) -> List[Dict[str, Any]]:
        payload = self._request("GET", "/v1/paper/accounts/", params={"include_archived": include_archived, "limit": limit})
        return self._results(payload)

    def create_account(self, *, name: str = "Paper Account", initial_cash: Union[str, float, int] = "100000") -> Dict[str, Any]:
        return self._request(
            "POST",
            "/v1/paper/accounts/",
            body={"name": name, "initial_cash": str(initial_cash)},
        )

    def get_account(self, account_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/v1/paper/accounts/{quote(str(account_id), safe='')}/")

    def update_account(self, account_id: str, *, name: str) -> Dict[str, Any]:
        return self._request("PATCH", f"/v1/paper/accounts/{quote(str(account_id), safe='')}/", body={"name": name})

    def delete_account(self, account_id: str) -> Dict[str, Any]:
        return self._request("DELETE", f"/v1/paper/accounts/{quote(str(account_id), safe='')}/")

    def reset_account(
        self,
        account_id: str,
        *,
        confirm: bool = True,
        initial_cash: Optional[Union[str, float, int]] = None,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"confirm": bool(confirm)}
        if initial_cash is not None:
            body["initial_cash"] = str(initial_cash)
        if reason:
            body["reason"] = reason
        return self._request("POST", f"/v1/paper/accounts/{quote(str(account_id), safe='')}/reset/", body=body)

    def account_summary(self, account_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/v1/paper/accounts/{quote(str(account_id), safe='')}/account/")

    def portfolio_history(self, account_id: str, **params: Any) -> List[Dict[str, Any]]:
        payload = self._request(
            "GET",
            f"/v1/paper/accounts/{quote(str(account_id), safe='')}/portfolio/history/",
            params=params or None,
        )
        return self._results(payload)

    def submit_order(self, account_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        body = dict(payload)
        if "qty" in body:
            body["qty"] = str(body["qty"])
        if body.get("limit_price") is not None:
            body["limit_price"] = str(body["limit_price"])
        return self._request("POST", f"/v1/paper/accounts/{quote(str(account_id), safe='')}/orders/", body=body)

    def place_stock_order(
        self,
        account_id: str,
        *,
        symbol: str,
        qty: Union[int, float, str],
        side: str,
        order_type: str = "market",
        time_in_force: str = "day",
        limit_price: Optional[Union[float, str]] = None,
        client_order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "symbol": str(symbol).upper(),
            "qty": str(qty),
            "side": side,
            "type": order_type,
            "time_in_force": time_in_force,
        }
        if limit_price is not None:
            payload["limit_price"] = str(limit_price)
        if client_order_id:
            payload["client_order_id"] = client_order_id
        return self.submit_order(account_id, payload)

    def place_option_order(
        self,
        account_id: str,
        *,
        symbol: str,
        qty: Union[int, float, str],
        side: str,
        position_intent: str,
        order_type: str = "market",
        time_in_force: str = "day",
        limit_price: Optional[Union[float, str]] = None,
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
            payload["limit_price"] = str(limit_price)
        if client_order_id:
            payload["client_order_id"] = client_order_id
        return self.submit_order(account_id, payload)

    def list_orders(self, account_id: str, **params: Any) -> List[Dict[str, Any]]:
        payload = self._request("GET", f"/v1/paper/accounts/{quote(str(account_id), safe='')}/orders/", params=params or None)
        return self._results(payload)

    def get_order(self, account_id: str, order_id: str) -> Dict[str, Any]:
        return self._request(
            "GET",
            f"/v1/paper/accounts/{quote(str(account_id), safe='')}/orders/{quote(str(order_id), safe='')}/",
        )

    def cancel_order(self, account_id: str, order_id: str) -> Dict[str, Any]:
        return self._request(
            "DELETE",
            f"/v1/paper/accounts/{quote(str(account_id), safe='')}/orders/{quote(str(order_id), safe='')}/",
        )

    def get_order_by_client_order_id(self, account_id: str, client_order_id: str) -> Dict[str, Any]:
        return self._request(
            "GET",
            f"/v1/paper/accounts/{quote(str(account_id), safe='')}/orders:by_client_order_id",
            params={"client_order_id": client_order_id},
        )

    def list_positions(self, account_id: str) -> List[Dict[str, Any]]:
        payload = self._request("GET", f"/v1/paper/accounts/{quote(str(account_id), safe='')}/positions/")
        return self._results(payload)

    def list_fills(self, account_id: str, **params: Any) -> List[Dict[str, Any]]:
        payload = self._request("GET", f"/v1/paper/accounts/{quote(str(account_id), safe='')}/fills/", params=params or None)
        return self._results(payload)

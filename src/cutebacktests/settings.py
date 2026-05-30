from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
from typing import Dict, Iterable, Optional


def _load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _to_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _normalize_alpaca_stock_feed(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"sip", "iex"}:
        return normalized
    return "sip"


def _normalize_alpaca_option_feed(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"opra", "indicative"}:
        return normalized
    return "opra"


@dataclass
class Settings:
    cutemarkets_api_key: str
    alpaca_api_key: str
    alpaca_secret_key: str

    cutemarkets_base_url: str

    alpaca_paper_base_url: str
    alpaca_data_base_url: str

    data_dir: Path
    db_path: Path
    log_level: str
    alpaca_stock_feed_name: str = "sip"
    alpaca_option_feed_name: str = "opra"
    cutemarkets_stocks_api_key: str = ""
    cutemarkets_paper_api_key: str = ""

    @classmethod
    def from_env(cls, env_path: str = ".env") -> "Settings":
        _load_env_file(Path(env_path))
        data_dir = Path(os.getenv("CUTEBACKTESTS_DATA_DIR", "data"))
        db_path = Path(os.getenv("CUTEBACKTESTS_DB_PATH", str(data_dir / "cutebacktests.duckdb")))
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        return cls(
            cutemarkets_api_key=os.getenv("CUTEMARKETS_API_KEY", ""),
            alpaca_api_key=os.getenv("ALPACA_API_KEY", ""),
            alpaca_secret_key=os.getenv("ALPACA_SECRET_KEY", ""),
            cutemarkets_base_url=os.getenv("CUTEMARKETS_BASE_URL", "https://api.cutemarkets.com"),
            alpaca_paper_base_url=os.getenv("ALPACA_PAPER_BASE_URL", "https://paper-api.alpaca.markets"),
            alpaca_data_base_url=os.getenv("ALPACA_DATA_BASE_URL", "https://data.alpaca.markets"),
            data_dir=data_dir,
            db_path=db_path,
            log_level=os.getenv("LOG_LEVEL", "DEBUG"),
            alpaca_stock_feed_name=_normalize_alpaca_stock_feed(os.getenv("ALPACA_STOCK_FEED", "sip")),
            alpaca_option_feed_name=_normalize_alpaca_option_feed(os.getenv("ALPACA_OPTION_FEED", "opra")),
            cutemarkets_stocks_api_key=os.getenv("CUTEMARKETS_STOCKS_API_KEY", os.getenv("CUTEMARKETS_API_KEY", "")),
            cutemarkets_paper_api_key=os.getenv("CUTEMARKETS_PAPER_API_KEY", os.getenv("CUTEMARKETS_API_KEY", "")),
        )

    def required_keys_present(self, keys: Optional[Iterable[str]] = None) -> Dict[str, bool]:
        field_map = {
            "cutemarkets": bool(self.cutemarkets_api_key),
            "cutemarkets_stocks": bool(self.cutemarkets_stocks_api_key or self.cutemarkets_api_key),
            "cutemarkets_paper": bool(self.cutemarkets_paper_api_key or self.cutemarkets_api_key),
            "alpaca": bool(self.alpaca_api_key and self.alpaca_secret_key),
        }
        if keys is None:
            return field_map
        return {key: field_map.get(key, False) for key in keys}

    def use_live_alpaca(self) -> bool:
        return _to_bool(os.getenv("ALPACA_USE_LIVE", "false"), default=False)

    def alpaca_stock_feed(self) -> str:
        return _normalize_alpaca_stock_feed(self.alpaca_stock_feed_name)

    def alpaca_option_feed(self) -> str:
        return _normalize_alpaca_option_feed(self.alpaca_option_feed_name)

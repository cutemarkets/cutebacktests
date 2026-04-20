<p align="center">
  <img src="https://cutemarkets.com/blog/blog-options-data.png" alt="CuteMarkets options research illustration" width="860">
</p>

# cutebacktests

Intraday options backtesting for U.S. equities.

`cutebacktests` is the public backtesting runtime behind CuteMarkets research: a DuckDB-backed engine, named opening-range profiles, and market-data adapters for reproducible strategy work on your own machine. It keeps the research stack public and usable without shipping the private orchestration and deployment code from the internal repo.

## Scope

- Intraday/options backtesting runtime
- Opening-range profile registry and profile helpers
- CuteMarkets/Alpaca-backed market-data adapters used by the runtime
- Walk-forward robustness helpers

This repository does **not** ship the congressional-disclosure engine, live/paper bots, remote server launch tooling, or phase orchestration from the private repo.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

## Configure

```bash
cp .env.example .env
```

Required credentials depend on the commands you run:

- `CUTEMARKETS_API_KEY`
- `ALPACA_API_KEY`
- `ALPACA_SECRET_KEY`

Package-local paths use:

- `CUTEBACKTESTS_DATA_DIR`
- `CUTEBACKTESTS_DB_PATH`

## Example

```python
from datetime import datetime

from cutebacktests import (
    IntradayOptionsBacktestConfig,
    IntradayOptionsBacktester,
    get_opening_range_profile,
)
from cutebacktests.providers import CuteMarketsProvider
from cutebacktests.settings import Settings
from cutebacktests.storage import DataStore

settings = Settings.from_env(".env")
store = DataStore(settings.db_path)
profile = get_opening_range_profile("c4_long_only_rr15")

try:
    backtester = IntradayOptionsBacktester(
        store=store,
        cutemarkets_provider=CuteMarketsProvider(settings),
    )
    result = backtester.run(
        IntradayOptionsBacktestConfig(
            ticker="SPY",
            start=datetime(2025, 1, 1),
            end=datetime(2025, 1, 31),
            return_trade_log=True,
            **profile.to_intraday_strategy_kwargs(),
        )
    )
    print("trades:", result["trades"])
finally:
    store.close()
```

If you want mixed-provider market-data surfaces, pass `alpaca_data_provider=AlpacaDataProvider(settings)` when you build the backtester.

## CLI

Show the public CLI:

```bash
python -m cutebacktests.cli --help
```

Run the intraday/options backtester directly:

```bash
python -m cutebacktests.cli run-intraday-options-backtest \
  --ticker SPY \
  --start 2025-01-01 \
  --end 2025-12-31
```

Run a named opening-range profile:

```bash
python -m cutebacktests.cli run-opening-range-profile-backtest \
  --profile-name c4_long_only_rr15 \
  --ticker SPY \
  --start 2025-01-01 \
  --end 2025-12-31
```

## Tests

```bash
PYTHONPATH=src python -m pytest tests/test_public_surface.py -q
```

## Documentation

- CuteMarkets Docs: [cutemarkets.com/docs/](https://cutemarkets.com/docs/)
- Repository: [github.com/cutemarkets/cutebacktests](https://github.com/cutemarkets/cutebacktests)

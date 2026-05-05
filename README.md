<p align="center">
  <img src="https://cutemarkets.com/blog/blog-options-data.png" alt="CuteMarkets options research illustration" width="860">
</p>

# cutebacktests: Historical and Intraday Options Backtesting Runtime

Historical options backtesting, intraday options backtesting, quote-aware backtesting, and walk-forward strategy research for U.S. equities. `cutebacktests` is the public runtime behind CuteMarkets research: a DuckDB-backed options backtester, a historical options feed, market-data adapters, and an opening-range profile registry that you can run on your own machine.

This repository is designed for developers and quantitative researchers who need more than chart-level ideas. It focuses on causal entry logic, historical contract reconstruction, options microstructure filters, and reproducible evaluation surfaces instead of paper-only strategy descriptions.

Quick links:

- [Read docs](https://cutemarkets.com/docs/cutebacktests)
- [Get API key](https://cutemarkets.com/signup)
- [Explore `cutemarkets-python`](https://github.com/cutemarkets/cutemarkets-python)
- [Explore `cute-intraday-option-strats`](https://github.com/cutemarkets/cute-intraday-option-strats)

## Scope

- Historical and intraday options backtest runtime
- Historical options feed for contract reconstruction and close snapshots
- CuteMarkets-backed market-data access for public examples and default workflows
- Optional compatibility layers for auxiliary providers
- Opening-range profile registry and profile helpers
- Walk-forward and robustness helpers

## Explore Examples

- [examples/run_intraday_options_backtest.py](examples/run_intraday_options_backtest.py)
- [examples/run_opening_range_profile.py](examples/run_opening_range_profile.py)
- [examples/historical_options_feed_demo.py](examples/historical_options_feed_demo.py)
- [examples/walk_forward_profile_eval.py](examples/walk_forward_profile_eval.py)

## In-Repo Documentation

- [docs/realism.md](docs/realism.md)
- [docs/profile-catalog.md](docs/profile-catalog.md)
- [docs/walk-forward.md](docs/walk-forward.md)

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

Optional compatibility workflows may also use:

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

If you need an auxiliary provider for a private workflow, the runtime still supports that path. The public examples and the default research path in this repo use CuteMarkets directly.

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

The public CLI uses CuteMarkets by default. Add `--with-alpaca` only if you explicitly want the auxiliary provider enabled.

Run a named opening-range profile:

```bash
python -m cutebacktests.cli run-opening-range-profile-backtest \
  --profile-name c4_long_only_rr15 \
  --ticker SPY \
  --start 2025-01-01 \
  --end 2025-12-31
```

Run the public walk-forward wrapper:

```bash
python -m cutebacktests.cli run-walk-forward-profile-backtest \
  --profile-name c4_long_only_rr15 \
  --ticker SPY \
  --start 2025-01-01 \
  --end 2025-12-31 \
  --output-dir tmp/walkforward_spy
```

Audit daily options tradability before a backtest:

```bash
python -m cutebacktests.cli sample-option-tradability \
  --ticker SPY \
  --end-day 2025-12-31 \
  --lookback-days 30 \
  --output-dir tmp/tradability_spy
```

## Tests

```bash
PYTHONPATH=src python -m pytest tests/test_public_surface.py -q
```

## Documentation

- CuteMarkets Docs: [cutemarkets.com/docs/](https://cutemarkets.com/docs/)
- Repository: [github.com/cutemarkets/cutebacktests](https://github.com/cutemarkets/cutebacktests)
- Python SDK: [github.com/cutemarkets/cutemarkets-python](https://github.com/cutemarkets/cutemarkets-python)
- Public model repo: [github.com/cutemarkets/cute-intraday-option-strats](https://github.com/cutemarkets/cute-intraday-option-strats)

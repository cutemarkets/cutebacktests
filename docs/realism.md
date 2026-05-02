# Realism in `cutebacktests`

`cutebacktests` is designed around causal, quote-aware research rather than optimistic chart replay. The public runtime does not assume that a strategy can fill at arbitrary prices on a signal bar, and it does not assume that historical options contracts can be reconstructed correctly from a current-day chain snapshot. Those two assumptions are where many superficial options backtests fail.

## Causal entry assumptions

The runtime is built to distinguish between signal detection and execution. Strategy logic can identify a setup on one bar and enter on a later bar open or with explicit execution delay controls. That keeps the public examples aligned with the actual engine semantics and avoids the common mistake of letting a backtest react to information that was not available at the time of the fill.

Execution timing controls in the public CLI and config surface include:

- `execution_entry_delay_minutes`
- `execution_exit_delay_minutes`
- `execution_delay_randomization`
- `use_option_quotes_for_fills`

These switches matter because the same stock-side signal can produce very different option outcomes once spread, delay, and contract quality are enforced.

## Quote-aware execution

Options fills are only credible if the runtime distinguishes between quotes, trades, and bars. The public backtester can use option quotes for fills, restrict entry spread, and fall back in controlled ways when quotes are incomplete. This is a better default than marking every option trade at bar close or midpoint regardless of observed liquidity.

In practice, that means research code should treat these fields as first-class constraints:

- entry spread
- quote coverage
- contract volume
- open interest
- entry-bar instability

Those controls are the difference between a chart pattern and a tradable options workflow.

## Why historical contract reconstruction matters

For historical options backtesting, a current-day option chain is not a valid substitute for the contracts that existed on the historical date being studied. The public historical feed in this repo reconstructs day-specific chains from historical contract listings plus historical quotes or bars. That design avoids the common failure mode where a provider returns today's active contracts while the researcher believes they are seeing the historical universe.

If you are backtesting earnings or short-dated intraday strategies, this point is not cosmetic. Contract availability, expiry alignment, and quote coverage can change the trade set materially.

## Practical implication

The public runtime is best used when you want to test a strategy under assumptions that can survive contact with real options data. It is still a research engine, not a guarantee of live performance, but it is intentionally harder to fool than a simple candle-level backtest.

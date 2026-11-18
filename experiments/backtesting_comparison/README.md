# Backtesting engine comparison prototype

This experiment evaluates Backtesting.py against a hand-worked synthetic dataset.
OpenAlgo is assessed separately from its documentation because its Analyzer is a
broker-data execution sandbox, not an interchangeable historical backtest engine.
No broker credentials or trading account are used.

## Reproduce

From the Karyo repository root:

```sh
uv run --isolated --no-project \
  --with-requirements experiments/backtesting_comparison/requirements.txt \
  python experiments/backtesting_comparison/run.py \
  --output experiments/backtesting_comparison/results.json
```

The first run downloads dependencies. Backtesting.py and the numerical libraries
are pinned separately from Karyo. Transitive dependencies are not fully locked;
the JSON report records Python and the core numerical-library versions. The
tested interpreter was Python 3.13.5 on macOS. Python 3.10 compatibility of this
optional experiment has not been established. Karyo's base dependencies and
lockfile are unchanged.

Successful execution prints verified JSON and exits zero. A mismatch raises an
assertion and exits nonzero before writing a new report. Re-running replaces the
specified report file. These files are an offline experiment, not an agent tool
or a new terminal command.

## Independent expected results

`prices.csv` contains nine synthetic daily bars for one fictional asset. Prices
deliberately gap between closes and opens so a wrong execution rule is visible.
Dates are labels, not evidence of real trading history. No external data is used.

The strategy buys ten whole units when the close rises, if flat, and closes the
position when the close falls. Decisions use only the current and previous
close; market orders fill on the following bar's open. There is no leverage,
shorting, spread, forced final liquidation, or open position at the end.

| Entry signal | Entry fill | Exit signal | Exit fill | Gross PnL |
| --- | --- | --- | --- | --- |
| Jan 7 | Jan 8: 10 × 110 | Jan 9 | Jan 10: 10 × 90 | -200 |
| Jan 13 | Jan 14: 10 × 100 | Jan 15 | Jan 16: 10 × 120 | +200 |

With initial cash of 10,000 arbitrary currency units, total traded notional is
4,200. A commission rate `c` charged on each entry and exit gives total costs
`4200 × c` and final equity `10000 - 4200 × c`. The lowest marked-to-market
equity occurs after the first exit: `9800 - 2000 × c`. Thus the expected maximum
drawdown percentage is `(200 + 2000 × c) / 10000 × 100`.

| Commission per side | Expected final equity | Observed final equity | Costs | Max drawdown | Result |
| --- | --- | --- | --- | --- | --- |
| 0% | 10,000.00 | 10,000.00 | 0.00 | 2.00% | Passed |
| 0.1% | 9,995.80 | 9,995.80 | 4.20 | 2.02% | Passed |
| 0.5% | 9,979.00 | 9,979.00 | 21.00 | 2.10% | Passed |

The script checks every closed trade's date, quantity, prices, commission, and
net PnL, plus trade count, total return, final equity, drawdown, and win rate.
It also changes the final bar and verifies that preceding equity and the first
completed trade stay unchanged. This checks one prefix, not every possible form
of future-data leakage. A negative control deliberately enables same-close
execution and confirms that the next-open oracle rejects it.

These are correctness checks, not a profitable strategy or an execution-speed
benchmark. Costs are illustrative; taxes, slippage, spreads, partial fills,
liquidity, market calendars, dividends, splits, and realistic broker constraints
are not modeled. No investment-performance conclusion follows from the fixture.

## Comparison and decision

| Criterion | Backtesting.py | OpenAlgo |
| --- | --- | --- |
| Evaluation performed | Executed locally against the fixture | Documentation review only; not installed or executed |
| Role | Historical strategy simulation, one asset at a time | Broker integration, historical-data storage/access, sandbox execution |
| Offline fixture test | Passed without network or credentials after installation | Analyzer needs active market-price services; same CSV replay not tested |
| Inputs | OHLC DataFrame and Python strategy | Application API key, application setup, and broker/data access where needed |
| Karyo integration | Optional deterministic adapter returning bounded JSON | Read-only REST history adapter first; authenticated MCP requires client changes |
| License identified | AGPL-3.0 | AGPL-3.0 |

Recommendation: use Backtesting.py for the first single-asset historical
simulation, subject to the chosen distribution/license approach. Keep it an
optional dependency and place a validated dataset boundary ahead of the engine.
Retain OpenAlgo as a candidate for Indian-market data and later paper trading.
This experiment does not establish OpenAlgo compatibility or compare runtime
performance between the two products.

The next implementation should load validated user-supplied data, use explicit
capital and cost assumptions, and return trade-level results through a bounded
tool. Map the terminal's total loss budget separately from position sizing; do
not claim it is an enforced cap. Multi-asset portfolio testing would require a
different engine evaluation.

## Primary references consulted

- [Backtesting.py API](https://kernc.github.io/backtesting.py/doc/backtesting/backtesting.html): next-open fills, commission charged at entry and exit, and finalization behavior.
- [Backtesting.py guide](https://kernc.github.io/backtesting.py/doc/examples/Quick%20Start%20User%20Guide.html): single-asset scope and OHLC input.
- [Backtesting.py repository and license](https://github.com/kernc/backtesting.py).
- [OpenAlgo Analyzer](https://docs.openalgo.in/new-features/api-analyzer): sandbox execution and broker market-data requirements.
- [OpenAlgo Historify](https://docs.openalgo.in/new-features/historify): local historical storage and exports.
- [OpenAlgo History API](https://docs.openalgo.in/api-documentation/v1/data-api/history): API key, broker/database sources, and date/interval fields.
- [OpenAlgo MCP](https://docs.openalgo.in/mcp): stdio/API-key and remote OAuth transports.
- [OpenAlgo repository and license](https://github.com/marketcalls/openalgo).

"""Compare an external engine with a hand-worked execution fixture.

Run with the adjacent requirements.txt in an isolated uv environment. This is
an engine correctness experiment, not a performance claim about a strategy.
"""

import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import sys

import pandas as pd
from backtesting import Backtest, Strategy


FIXTURE = Path(__file__).with_name('prices.csv')
CASH = 10000
QUANTITY = 10
# Worked independently: signal on Jan 7 -> buy Jan 8 open; signal on Jan 9
# -> sell Jan 10 open. Repeat Jan 13 -> Jan 14, Jan 15 -> Jan 16.
EXPECTED_TRADES = [
    {'entry_date': '2025-01-08', 'exit_date': '2025-01-10', 'entry': 110, 'exit': 90},
    {'entry_date': '2025-01-14', 'exit_date': '2025-01-16', 'entry': 100, 'exit': 120},
]


class OneBarMomentum(Strategy):
    """Long 10 units on a rising close; exit on a falling close. No shorts."""

    def init(self):
        pass

    def next(self):
        if self.data.Close[-1] > self.data.Close[-2] and not self.position:
            self.buy(size=QUANTITY)
        elif self.data.Close[-1] < self.data.Close[-2] and self.position:
            self.position.close()


def load_fixture():
    frame = pd.read_csv(FIXTURE, index_col='date', parse_dates=True)
    frame.columns = [column.title() for column in frame.columns]
    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.hasnans:
        raise ValueError('Fixture dates must be valid')
    if not frame.index.is_unique or not frame.index.is_monotonic_increasing:
        raise ValueError('Fixture dates must be unique and ascending')
    for column in ('Open', 'High', 'Low', 'Close', 'Volume'):
        values = pd.to_numeric(frame[column], errors='raise')
        if values.isna().any() or not values.map(lambda x: float('-inf') < x < float('inf')).all():
            raise ValueError(f'Nonfinite fixture values in {column}')
        if (values < 0).any() or (column != 'Volume' and (values == 0).any()):
            raise ValueError(f'Invalid fixture values in {column}')
    if (frame.High < frame[['Open', 'Close', 'Low']].max(axis=1)).any() or (
            frame.Low > frame[['Open', 'Close', 'High']].min(axis=1)).any():
        raise ValueError('Inconsistent OHLC fixture')
    return frame


def simulate(frame, commission, trade_on_close=False):
    return Backtest(
        frame, OneBarMomentum, cash=CASH, commission=float(commission),
        spread=0, margin=1, trade_on_close=trade_on_close, exclusive_orders=True,
        finalize_trades=False,
    ).run()


def require_equal(label, actual, expected, tolerance=1e-8):
    if abs(float(actual) - float(expected)) > tolerance:
        raise AssertionError(f'{label}: expected {expected}, got {actual}')


def check_case(frame, commission, trade_on_close=False):
    stats = simulate(frame, commission, trade_on_close)
    trades = stats['_trades']
    require_equal('closed trade count', len(trades), len(EXPECTED_TRADES))
    expected_equity = Decimal(CASH)
    expected_costs = Decimal(0)
    actual_trades = []
    for (_, actual), expected in zip(trades.iterrows(), EXPECTED_TRADES):
        entry_date = actual.EntryTime.strftime('%Y-%m-%d')
        exit_date = actual.ExitTime.strftime('%Y-%m-%d')
        if (entry_date, exit_date) != (expected['entry_date'], expected['exit_date']):
            raise AssertionError('Execution dates differ from hand-worked next-open fills')
        for field, target in [('Size', QUANTITY), ('EntryPrice', expected['entry']), ('ExitPrice', expected['exit'])]:
            require_equal(field, actual[field], target)
        gross = Decimal(QUANTITY) * (Decimal(expected['exit']) - Decimal(expected['entry']))
        costs = Decimal(QUANTITY) * (Decimal(expected['entry']) + Decimal(expected['exit'])) * commission
        require_equal('commission', actual.Commission, costs)
        require_equal('net PnL', actual.PnL, gross - costs)
        expected_equity += gross - costs
        expected_costs += costs
        actual_trades.append({
            'entry_date': entry_date, 'exit_date': exit_date,
            'quantity': int(actual.Size), 'entry_price': float(actual.EntryPrice),
            'exit_price': float(actual.ExitPrice), 'costs': float(actual.Commission),
            'net_pnl': float(actual.PnL),
        })
    require_equal('final equity', stats['Equity Final [$]'], expected_equity)
    require_equal('return percent', stats['Return [%]'], (expected_equity / CASH - 1) * 100)
    # Lowest equity occurs after the first exit: 10,000 - 200 - 2,000 * fee.
    expected_drawdown_pct = (Decimal(200) + Decimal(2000) * commission) / CASH * 100
    require_equal('maximum drawdown', -stats['Max. Drawdown [%]'], expected_drawdown_pct)
    require_equal('win rate', stats['Win Rate [%]'], 50)
    return {
        'commission_rate_per_side': float(commission), 'trades': actual_trades,
        'expected_final_equity': float(expected_equity),
        'actual_final_equity': float(stats['Equity Final [$]']),
        'total_costs': float(expected_costs), 'return_pct': float(stats['Return [%]']),
        'maximum_drawdown_pct': float(-stats['Max. Drawdown [%]']),
        'verification': 'passed',
    }


def check_future_independence(frame):
    baseline = simulate(frame, Decimal('0.001'))
    changed = frame.copy(deep=True)
    # Change only the last bar. Earlier equity and completed trades must agree.
    changed.iloc[-1, changed.columns.get_indexer(['Open', 'High', 'Low', 'Close'])] = [80, 81, 69, 70]
    perturbed = simulate(changed, Decimal('0.001'))
    pd.testing.assert_series_equal(
        baseline['_equity_curve'].Equity.iloc[:-1],
        perturbed['_equity_curve'].Equity.iloc[:-1],
    )
    pd.testing.assert_series_equal(baseline['_trades'].iloc[0], perturbed['_trades'].iloc[0])
    return 'passed for the checked prefix; not a general proof against lookahead bias'


def check_negative_control(frame):
    try:
        check_case(frame, Decimal('0.001'), trade_on_close=True)
    except AssertionError:
        return 'passed: same-close execution rejected by the next-open oracle'
    raise AssertionError('Negative control unexpectedly passed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Write the verified JSON report to this path')
    args = parser.parse_args()
    frame = load_fixture()
    # Reserve stdout for machine-readable JSON; engine progress goes to stderr.
    with redirect_stdout(sys.stderr):
        cases = [check_case(frame, Decimal(rate)) for rate in ('0', '0.001', '0.005')]
        future_check = check_future_independence(frame)
        negative_control = check_negative_control(frame)
    report = {
        'experiment': 'synthetic next-open execution and cost verification',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'python': platform.python_version(),
        'versions': {name: version(name) for name in ('backtesting', 'pandas', 'numpy')},
        'dataset': {'path': 'experiments/backtesting_comparison/prices.csv',
                    'sha256': hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
                    'synthetic': True, 'rows': len(frame), 'currency': 'arbitrary units'},
        'initial_cash': CASH, 'quantity': QUANTITY,
        'execution': 'long-only; next-bar open; no leverage; zero spread; no forced final liquidation',
        'cases': cases, 'future_data_perturbation_check': future_check,
        'wrong_execution_negative_control': negative_control,
        'limitations': [
            'Synthetic execution fixture, not evidence of profitability.',
            'Costs are illustrative flat commissions, not broker or jurisdiction-specific taxes.',
            'No slippage, bid-ask spread, liquidity limits, dividends, or corporate actions modeled.',
            'No strategy optimization, real data, paper-trading account, or broker connection tested.',
            'OpenAlgo was reviewed from documentation, not executed.',
        ],
    }
    rendered = json.dumps(report, indent=2, allow_nan=False) + '\n'
    if args.output:
        args.output.write_text(rendered, encoding='utf-8')
    print(rendered, end='')


if __name__ == '__main__':
    main()

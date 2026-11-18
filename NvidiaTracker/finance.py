"""Small, testable financial calculations. No network calls or UI here."""
import math
from zoneinfo import ZoneInfo
import pandas as pd

RATING_COLUMNS = ['strongBuy', 'buy', 'hold', 'sell', 'strongSell']
RATING_LABELS = ['Strong Buy', 'Buy', 'Hold', 'Sell', 'Strong Sell']


def number(value, positive=False):
    """Reject missing, infinite, boolean, and (optionally) nonpositive values."""
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
        if not math.isfinite(value) or (positive and value <= 0):
            return None
        return value
    except (TypeError, ValueError, OverflowError):
        return None


def price_change(price, previous_close):
    """Dollar change and percentage change versus the official previous close."""
    price = number(price, positive=True)
    previous_close = number(previous_close, positive=True)
    if price is None or previous_close is None:
        return None, None
    change = price - previous_close
    percent = change / previous_close * 100
    if not math.isfinite(change) or not math.isfinite(percent):
        return None, None
    return change, percent


def analyst_summary(frame):
    """Only use Yahoo's current (0m) row; never substitute old or missing counts."""
    if not isinstance(frame, pd.DataFrame) or frame.empty or 'period' not in frame.columns:
        return None
    current = frame.loc[frame['period'] == '0m']
    if current.empty:
        return None
    counts = [number(current.iloc[0].get(key)) for key in RATING_COLUMNS]
    if any(n is None or n < 0 or not n.is_integer() for n in counts):
        return None
    counts = [int(n) for n in counts]
    total = sum(counts)
    if total == 0:
        return None
    # A transparent app-calculated consensus, not a proprietary Yahoo score.
    score = sum((i + 1) * n for i, n in enumerate(counts)) / total
    index = min(4, int(score + 0.5) - 1)
    return {'counts': counts, 'total': total, 'score': score,
            'label': RATING_LABELS[index],
            'buy': counts[0] + counts[1], 'hold': counts[2],
            'sell': counts[3] + counts[4]}


def clean_history(frame):
    """Sort price observations, remove duplicates, and discard invalid prices."""
    if not isinstance(frame, pd.DataFrame) or frame.empty or 'Close' not in frame.columns:
        return pd.DataFrame(columns=['Close'])
    result = frame[['Close']].copy()
    if not isinstance(result.index, pd.DatetimeIndex):
        return pd.DataFrame(columns=['Close'])
    result = result.loc[result.index.notna()]
    result['Close'] = pd.to_numeric(result['Close'], errors='coerce')
    result = result.loc[result['Close'].map(lambda x: number(x, True) is not None)]
    return result.loc[~result.index.duplicated(keep='last')].sort_index()


def describe_session(now, schedule):
    """Classify the scheduled regular session, including holidays and early closes."""
    if schedule.empty:
        return 'Market closed', 'No regular trading session today.'
    opening, closing = schedule.iloc[0][['market_open', 'market_close']]
    if opening <= now < closing:
        closing_et = closing.tz_convert(ZoneInfo('America/New_York'))
        return 'Market open', f'Regular session closes {closing_et:%I:%M %p %Z}.'
    return 'Market closed', 'Outside regular trading hours. Extended-hours prices are excluded.'

"""Synthetic test inputs only; these are never displayed by the application."""
import unittest
import pandas as pd
import pandas_market_calendars as mcal
from finance import price_change, analyst_summary, clean_history, describe_session, RATING_COLUMNS, RATING_LABELS


def rating_frame(counts, period='0m'):
    return pd.DataFrame([dict(period=period, **dict(zip(RATING_COLUMNS, counts)))])


class FinanceTests(unittest.TestCase):
    def test_returns(self):
        for price, change in [(110, 10), (90, -10), (100, 0)]:
            self.assertEqual(price_change(price, 100), (change, change))
        self.assertAlmostEqual(price_change(155.46, 156.14)[1], -0.435506596644)

    def test_invalid_prices(self):
        for value in [None, 0, -1, float('nan'), float('inf'), 'invalid', True]:
            self.assertEqual(price_change(100, value), (None, None))
            self.assertEqual(price_change(value, 100), (None, None))
        self.assertEqual(price_change(1e308, 1e-308), (None, None))

    def test_consensus_totals(self):
        summary = analyst_summary(rating_frame([10, 5, 3, 1, 1]))
        self.assertEqual(summary['total'], 20)
        self.assertEqual((summary['buy'], summary['hold'], summary['sell']), (15, 3, 2))
        self.assertEqual(summary['label'], 'Buy')
        self.assertAlmostEqual(summary['score'], 1.9)

    def test_all_consensus_labels(self):
        for index, label in enumerate(RATING_LABELS):
            counts = [0] * 5
            counts[index] = 10
            self.assertEqual(analyst_summary(rating_frame(counts))['label'], label)

    def test_consensus_half_point_boundaries(self):
        for index in range(4):
            counts = [0] * 5
            counts[index:index+2] = [1, 1]
            self.assertEqual(analyst_summary(rating_frame(counts))['label'], RATING_LABELS[index+1])

    def test_missing_invalid_and_old_ratings(self):
        frames = [None, [], pd.DataFrame(), rating_frame([0,0,0,0,0]),
                  rating_frame([10,0,0,0,0], '-1m'), rating_frame([10,None,0,0,0]),
                  rating_frame([10,-1,0,0,0]), rating_frame([10,1.5,0,0,0]),
                  pd.DataFrame([dict(period='0m', strongBuy=10)])]
        for frame in frames:
            self.assertIsNone(analyst_summary(frame))

    def test_only_current_ratings_are_counted(self):
        frame = pd.concat([rating_frame([100,0,0,0,0], '-1m'), rating_frame([0,0,3,0,0])])
        self.assertEqual(analyst_summary(frame)['total'], 3)
        self.assertEqual(analyst_summary(frame)['label'], 'Hold')

    def test_history_cleanup(self):
        dates = pd.to_datetime(['2025-01-01','2025-01-03','2025-01-02','2025-01-04','2025-01-03',None])
        frame = pd.DataFrame({'Close':[0,101,100,float('inf'),102,104]}, index=dates)
        result = clean_history(frame)
        self.assertEqual(list(result.index.day), [2,3])
        self.assertEqual(list(result.Close), [100,102])

    def test_invalid_history(self):
        for frame in [None, [], pd.DataFrame(), pd.DataFrame({'Close':[100]}, index=['bad-date'])]:
            self.assertTrue(clean_history(frame).empty)

    def test_regular_market_boundaries(self):
        day = '2026-11-17'
        schedule = mcal.get_calendar('NASDAQ').schedule(start_date=day, end_date=day)
        for clock, expected in [('09:29:59','Market closed'), ('09:30:00','Market open'),
                                ('15:59:59','Market open'), ('16:00:00','Market closed')]:
            now = pd.Timestamp(f'{day} {clock}', tz='America/New_York')
            self.assertEqual(describe_session(now, schedule)[0], expected)

    def test_holiday_weekend_and_early_close(self):
        calendar = mcal.get_calendar('NASDAQ')
        for day in ['2026-11-14', '2026-11-26']:
            schedule = calendar.schedule(start_date=day, end_date=day)
            self.assertEqual(describe_session(pd.Timestamp(day, tz='UTC'), schedule)[0], 'Market closed')
        day = '2026-11-27'  # Friday after Thanksgiving: 1 PM Eastern close.
        schedule = calendar.schedule(start_date=day, end_date=day)
        for clock, expected in [('12:59:59','Market open'), ('13:00:00','Market closed')]:
            self.assertEqual(describe_session(pd.Timestamp(f'{day} {clock}', tz='America/New_York'), schedule)[0], expected)


if __name__ == '__main__':
    unittest.main()

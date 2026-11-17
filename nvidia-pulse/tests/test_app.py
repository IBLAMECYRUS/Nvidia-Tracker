"""Headless UI and integration checks. Synthetic fixtures never enter the app."""
import json
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
APP = str(Path(__file__).resolve().parents[1] / 'app.py')


class Provider:
    def __init__(self, prices=None, info=None, ratings_error=False):
        self.prices = prices if prices is not None else [100,105,110]
        self.info = info if info is not None else dict(regularMarketPrice=110,
            regularMarketPreviousClose=100, regularMarketTime=1700000000,
            targetMeanPrice=120, numberOfAnalystOpinions=20)
        self.ratings_error = ratings_error
        self.calls = dict(quote=0, history=0, analysts=0)
        self.history_options = []

    def get_info(self):
        self.calls['quote'] += 1
        return self.info

    def history(self, **kwargs):
        self.calls['history'] += 1
        self.history_options.append(kwargs)
        return pd.DataFrame({'Close':self.prices}, index=pd.date_range(
            '2025-01-06 09:30', periods=len(self.prices), tz='America/New_York'))

    def get_recommendations_summary(self):
        self.calls['analysts'] += 1
        if self.ratings_error:
            raise RuntimeError('Analyst service unavailable')
        return pd.DataFrame([dict(period='0m',strongBuy=10,buy=5,hold=3,sell=1,strongSell=1)])


class UITests(unittest.TestCase):
    def setUp(self):
        st.cache_data.clear()

    def render(self):
        app = AppTest.from_file(APP).run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        return app

    def text(self, app):
        return '\n'.join(x.value for x in app.markdown)

    def test_all_periods_and_cache(self):
        provider = Provider()
        with patch('yfinance.Ticker', return_value=provider):
            app = self.render()
            for period, expected in [('1 Day',('1d','5m')), ('1 Week',('5d','30m')),
                    ('3 Months',('3mo','1d')), ('1 Year',('1y','1d')), ('5 Years',('5y','1wk'))]:
                app.radio[0].set_value(period).run()
                self.assertEqual(len(app.exception), 0)
                call = provider.history_options[-1]
                self.assertEqual((call['period'],call['interval']), expected)
                self.assertFalse(call['auto_adjust'])
                self.assertFalse(call['prepost'])
            self.assertEqual(provider.calls, dict(quote=1,history=6,analysts=1))
            app.radio[0].set_value('1 Month').run()
            self.assertEqual(provider.calls['history'], 6)

    def test_refresh_and_cooldown(self):
        provider = Provider()
        with patch('yfinance.Ticker', return_value=provider):
            app = self.render()
            provider.info['regularMarketPrice'] = 115
            app.button[0].click().run()
            self.assertEqual(provider.calls, dict(quote=2,history=2,analysts=2))
            self.assertIn('$115.00', self.text(app))
            app.button[0].click().run()
            self.assertEqual(provider.calls, dict(quote=2,history=2,analysts=2))
            self.assertTrue(any('15 seconds' in x.value for x in app.info))

    def test_chart_axis_dates_and_return(self):
        with patch('yfinance.Ticker', return_value=Provider()):
            app = self.render()
            chart = json.loads(app.get('plotly_chart')[0].proto.spec)
            self.assertFalse(chart['layout']['yaxis']['autorange'])
            self.assertGreater(chart['layout']['yaxis']['range'][0], 0)
            self.assertEqual(chart['data'][0]['line']['color'], '#9BDF46')
            self.assertNotIn('%H', chart['data'][0]['hovertemplate'])
            self.assertIn('+10.00%', self.text(app))
            app.radio[0].set_value('1 Day').run()
            chart = json.loads(app.get('plotly_chart')[0].proto.spec)
            self.assertIn('%H:%M ET', chart['data'][0]['hovertemplate'])
            self.assertIn('09:30:00', chart['data'][0]['x'][0])

    def test_negative_flat_and_single_point_charts(self):
        for prices, color in [([110,105,100],'#FF737E'), ([100,100],'#94A299'), ([100],'#94A299')]:
            st.cache_data.clear()
            with patch('yfinance.Ticker', return_value=Provider(prices=prices)):
                app = self.render()
                chart = json.loads(app.get('plotly_chart')[0].proto.spec)
                self.assertEqual(chart['data'][0]['line']['color'], color)
                low, high = chart['layout']['yaxis']['range']
                self.assertLess(low, high)
                if len(prices) == 1:
                    self.assertEqual(chart['data'][0]['mode'], 'markers')
                    self.assertTrue(any('Only one observation' in x.value for x in app.caption))

    def test_unavailable_provider(self):
        with patch('yfinance.Ticker', side_effect=RuntimeError('Network unavailable')):
            app = self.render()
            self.assertGreaterEqual(len(app.warning), 1)
            self.assertGreaterEqual(len(app.info), 2)
            self.assertEqual(len(app.get('plotly_chart')), 0)

    def test_analyst_failure_keeps_quote_and_history(self):
        with patch('yfinance.Ticker', return_value=Provider(ratings_error=True)):
            app = self.render()
            self.assertIn('$110.00', self.text(app))
            self.assertEqual(len(app.get('plotly_chart')), 1)
            self.assertTrue(any('Analyst data' in x.value for x in app.info))

    def test_missing_quote_fields(self):
        with patch('yfinance.Ticker', return_value=Provider(info={'regularMarketPrice':110})):
            app = self.render()
            self.assertIn('Daily change unavailable', self.text(app))
            self.assertIn('Quote as of Unavailable', self.text(app))
            self.assertTrue(any('price target unavailable' in x.value for x in app.caption))

    def test_empty_and_malformed_data(self):
        with patch('yfinance.Ticker', return_value=Provider(prices=[], info=['bad schema'])):
            app = self.render()
            self.assertGreaterEqual(len(app.warning), 1)
            self.assertTrue(any('No price history' in x.value for x in app.info))


if __name__ == '__main__':
    unittest.main()

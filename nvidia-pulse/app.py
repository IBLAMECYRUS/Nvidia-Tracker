"""NVIDIA Pulse — a small Python for Finance project. Run: streamlit run app.py"""
from datetime import datetime, timezone
from html import escape
from zoneinfo import ZoneInfo
import time

import pandas as pd
import pandas_market_calendars as mcal
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from finance import number, price_change, analyst_summary, clean_history, describe_session, RATING_LABELS

st.set_page_config(page_title='NVIDIA Pulse', page_icon='🟢', layout='centered')


ET = ZoneInfo('America/New_York')
GREEN, RED, MUTED = '#9BDF46', '#FF737E', '#94A299'
PERIODS = {'1 Day': ('1d', '5m'), '1 Week': ('5d', '30m'),
           '1 Month': ('1mo', '1d'), '3 Months': ('3mo', '1d'),
           '1 Year': ('1y', '1d'), '5 Years': ('5y', '1wk')}


def now_utc():
    return datetime.now(timezone.utc)


def timestamp(value):
    if value is None:
        return 'Unavailable'
    try:
        moment = pd.Timestamp(value)
        if moment.tzinfo is None:
            return moment.strftime('%b %d, %Y')
        return moment.tz_convert(ET).strftime('%b %d, %Y · %I:%M %p %Z')
    except (ValueError, TypeError, OverflowError):
        return 'Unavailable'


def dollars(value):
    value = number(value, True)
    return f'${value:,.2f}' if value is not None else '—'


@st.cache_data(ttl=60, show_spinner=False)
def fetch_quote():
    # Yahoo provides regular-session price, timestamp, and previous official close.
    try:
        info = yf.Ticker('NVDA').get_info()
        if not isinstance(info, dict):
            raise ValueError('Unexpected quote response')
        return info, now_utc(), None
    except Exception:
        return {}, now_utc(), 'Quote data is unavailable. Yahoo may be temporarily limiting requests.'


@st.cache_data(ttl=300, show_spinner=False)
def fetch_history(label):
    period, interval = PERIODS[label]
    try:
        # auto_adjust=False keeps Close split-adjusted but not dividend-adjusted.
        # prepost=False keeps the chart consistent with the regular-session quote.
        data = yf.Ticker('NVDA').history(period=period, interval=interval,
                    auto_adjust=False, prepost=False, actions=False, timeout=12)
        return clean_history(data), now_utc(), None
    except Exception:
        return pd.DataFrame(), now_utc(), 'Price history is temporarily unavailable.'


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_analysts():
    try:
        frame = yf.Ticker('NVDA').get_recommendations_summary()
        return analyst_summary(frame), now_utc(), None
    except Exception:
        return None, now_utc(), 'Analyst data is temporarily unavailable from Yahoo Finance.'


@st.cache_data(ttl=86400, show_spinner=False)
def market_schedule(day):
    # Cache the calendar, not the clock: status changes exactly at open/close.
    return mcal.get_calendar('NASDAQ').schedule(start_date=day, end_date=day)


def market_status(now=None):
    # The NASDAQ calendar accounts for weekends, exchange holidays and early closes.
    now = now or now_utc()
    day = now.astimezone(ET).date()
    try:
        schedule = market_schedule(day)
        return describe_session(now, schedule)
    except Exception:
        return 'Market status unavailable', 'Exchange calendar could not be loaded.'


st.markdown('''<style>
.block-container {max-width: 900px; padding-top: 2.1rem; padding-bottom: 3rem;}
header[data-testid="stHeader"] {background: transparent;}
.brand {font-size: 1rem; font-weight: 750; letter-spacing: .16em; color: #f1f5f0;}
.brand span {color:#9bdf46;}
.eyebrow {color:#94a299; font-size:.72rem; letter-spacing:.13em; text-transform:uppercase;}
.hero {text-align:center; padding:25px; background:linear-gradient(130deg,#1b251c,#111713 70%); border:1px solid #2a382d; border-radius:22px; margin:14px 0;}
.company {font-size:1.1rem; font-weight:600; margin:10px 0 5px;}
.price {font-size:clamp(2.8rem,10vw,4.4rem); letter-spacing:-.055em; line-height:1.2; font-weight:350;}
.change {font-size:1rem; margin-top:8px; font-weight:600;}
.small {font-size:.8rem; color:#a8b6ac; margin-top:14px; line-height:1.65;}
.badge {display:inline-block; padding:5px 10px; border:1px solid #36473a; border-radius:30px; font-size:.72rem; color:#c4d2c7; margin:4px 4px 0 0;}
.stats {display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin:16px 0;}
.stat {background:#151b17; border:1px solid #29332c; border-radius:14px; padding:14px 12px;}
.stat b {display:block;font-size:1.45rem;margin-top:5px;}
.stat span {color:#a8b6ac;font-size:.78rem;}
div.stButton > button {min-height:46px; border-radius:12px;}
div[data-testid="stRadio"] label {min-height:44px; padding:6px 4px;}
div[data-testid="stVerticalBlockBorderWrapper"] > div {border-radius:18px;}
h3 {font-weight:600 !important; letter-spacing:-.025em;}
@media(max-width:600px){.block-container {padding:3.5rem 1rem 2rem;} .hero{padding:20px;} .stat{padding:12px 9px;} .stat b{font-size:1.25rem;}}
</style>''', unsafe_allow_html=True)

st.markdown('<div class="brand">◉ NVIDIA <span>PULSE</span></div>', unsafe_allow_html=True)
st.caption('A clearer view of NVDA. Price, perspective, and the Street.')
if st.button('↻  Refresh Data', width='stretch'):
    # Clear all financial caches so the selected chart and ratings refresh together.
    last_click = st.session_state.get('last_refresh_click', 0)
    if time.time() - last_click >= 15:
        fetch_quote.clear()
        fetch_history.clear()
        fetch_analysts.clear()
        market_schedule.clear()
        st.session_state.last_refresh_click = time.time()
    else:
        st.info('Please wait 15 seconds between manual refreshes.')

with st.spinner('Checking Yahoo Finance…'):
    info, quote_fetched, quote_error = fetch_quote()
price = number(info.get('regularMarketPrice'), True)
previous = number(info.get('regularMarketPreviousClose'), True)
change, pct = price_change(price, previous)
quote_epoch = number(info.get('regularMarketTime'), True)
try:
    quote_time = datetime.fromtimestamp(quote_epoch, timezone.utc) if quote_epoch else None
except (ValueError, OverflowError, OSError):
    quote_time = None
status, status_detail = market_status()
color = GREEN if change is not None and change > 0 else RED if change is not None and change < 0 else MUTED
change_text = f'{change:+,.2f} USD ({pct:+.2f}%)' if change is not None else 'Daily change unavailable'
lag = number(info.get('exchangeDataDelayedBy'))
delay_text = f'Provider-reported delay: {lag:g} min' if lag is not None and lag >= 0 else 'May be delayed · real-time not verified'

st.markdown(f'''<div class="hero"><div class="eyebrow">NASDAQ: NVDA · USD</div>
<div class="company">NVIDIA Corporation</div><div class="price">{dollars(price)}</div>
<div class="change" style="color:{color}">{change_text} <span style="color:#94a299;font-weight:400">vs previous close</span></div>
<div class="small">Previous official close <strong>{dollars(previous)}</strong><br>
Quote as of {escape(timestamp(quote_time))}</div>
<span class="badge">{status}</span><span class="badge">Regular-session quote</span>
</div>''', unsafe_allow_html=True)
st.caption(f'{delay_text}. {status_detail}')
if quote_error or price is None:
    st.warning(quote_error or 'The provider did not return a valid latest price. No estimated price is shown.')
if quote_time and (now_utc() - quote_time).total_seconds() > 900:
    st.caption('This is an older quote, not a live tick. Closed markets retain the last available regular-session price.')
st.caption(f'Quote request checked: {timestamp(quote_fetched)}')

with st.container(border=True):
    st.subheader('Price performance')
    label = st.radio('Time period', list(PERIODS), index=2, horizontal=True)
    with st.spinner('Loading price history…'):
        history, history_fetched, history_error = fetch_history(label)
    if history.empty:
        st.info(history_error or 'No price history is available for this period. Try Refresh Data later.')
    else:
        first, last = float(history.Close.iloc[0]), float(history.Close.iloc[-1])
        _, period_pct = price_change(last, first)
        line_color = GREEN if period_pct > 0 else RED if period_pct < 0 else MUTED
        if len(history) > 1:
            st.markdown(f'**{period_pct:+.2f}%** · first to last displayed observation')
        else:
            st.caption('Only one observation is available; a period return cannot yet be calculated.')
        # Linear interpolation avoids inventing peaks between observed prices.
        intraday = label in ('1 Day', '1 Week')
        # Normalize intraday values to Eastern wall time for browser-independent labels.
        chart_times = history.index
        if chart_times.tz is not None:
            chart_times = chart_times.tz_convert(ET).tz_localize(None)
        date_format = '%b %d, %Y %H:%M ET' if intraday else '%b %d, %Y'
        fig = go.Figure(go.Scatter(x=chart_times, y=history.Close,
                    mode='lines' if len(history) > 1 else 'markers',
                    marker=dict(color=line_color, size=8),
                    line=dict(color=line_color, width=2.5), fill='tozeroy',
                    fillcolor='rgba(155,223,70,0.045)' if period_pct >= 0 else 'rgba(255,115,126,0.045)',
                    hovertemplate='%{x|' + date_format + '}<br>$%{y:,.2f}<extra>NVDA</extra>'))
        fig.update_layout(height=310, margin=dict(l=0,r=8,t=12,b=0),
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color=MUTED), hovermode='x unified', dragmode=False,
                    xaxis=dict(showgrid=False, fixedrange=True, nticks=4),
                    yaxis=dict(side='right', tickprefix='$', gridcolor='#243027',
                               fixedrange=True, autorange=True, rangemode='normal'))
        # Explicit y range prevents the area fill from forcing a zero baseline.
        low, high = history.Close.min(), history.Close.max()
        pad = max((high-low)*.15, last*.005)
        fig.update_yaxes(range=[low-pad, high+pad], autorange=False)
        st.plotly_chart(fig, width='stretch', config={'displayModeBar':False, 'scrollZoom':False})
        chart_date = timestamp(history.index[-1]) if intraday else history.index[-1].strftime('%b %d, %Y')
        date_label = 'Latest bar starts' if intraday else 'Latest week starts' if label == '5 Years' else 'Latest trading date'
        st.caption(f'{date_label}: {chart_date}. '
                   'Split-adjusted closing prices; dividends excluded. Intraday times are Eastern.')
        if label == '1 Day':
            st.caption('Most recent available regular session · 5-minute bars. Bar timestamps indicate interval starts.')
        elif label == '1 Week':
            st.caption('Last 5 trading sessions · 30-minute bars.')
        elif label == '5 Years':
            st.caption('Weekly observations; timestamps label the start of each weekly interval.')
    st.caption(f'History request checked: {timestamp(history_fetched)}')

with st.container(border=True):
    st.subheader('Analyst Consensus')
    st.caption('WALL STREET · CURRENT PROVIDER SNAPSHOT')
    with st.spinner('Checking analyst ratings…'):
        summary, analysts_fetched, analysts_error = fetch_analysts()
    if summary is None:
        st.info(analysts_error or 'Current analyst counts are unavailable. No consensus rating has been invented.')
    else:
        consensus_color = GREEN if summary['score'] < 2.5 else RED if summary['score'] >= 3.5 else '#B6BDA8'
        st.markdown(f"<div style='border:1px solid {consensus_color};background:#1c2b20;border-radius:70px;width:130px;height:130px;display:flex;align-items:center;justify-content:center;text-align:center;font-size:1.65rem;color:{consensus_color};margin:14px auto;'>{summary['label']}</div>", unsafe_allow_html=True)
        st.caption(f"Calculated from {summary['total']} reported ratings · score {summary['score']:.2f} / 5")
        st.markdown(f'''<div class="stats">
        <div class="stat"><span>Buy + Strong Buy</span><b style="color:{GREEN}">{summary['buy']}</b></div>
        <div class="stat"><span>Hold</span><b>{summary['hold']}</b></div>
        <div class="stat"><span>Sell + Strong Sell</span><b style="color:{RED}">{summary['sell']}</b></div>
        </div>''', unsafe_allow_html=True)
        bars = go.Figure(go.Bar(x=summary['counts'], y=RATING_LABELS, orientation='h',
                    marker_color=[GREEN,'#6EBF62','#B6BDA8','#E99670',RED],
                    text=[f'{n} · {n / summary["total"]:.1%}' for n in summary['counts']], textposition='outside', cliponaxis=False,
                    hovertemplate='%{y}: %{x} analysts<extra></extra>'))
        bars.update_layout(height=235, margin=dict(l=0,r=85,t=8,b=10),
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#BAC7BF'), xaxis=dict(visible=False, fixedrange=True),
                    yaxis=dict(autorange='reversed', fixedrange=True), bargap=.45, dragmode=False)
        st.plotly_chart(bars, width='stretch', config={'displayModeBar':False})
    target = number(info.get('targetMeanPrice'), True)
    if target:
        st.markdown(f'**Average analyst target: {dollars(target)}**')
        _, upside = price_change(target, price)
        if upside is not None:
            st.write(f'{upside:+.2f}% implied upside/downside versus the displayed quote.')
        target_count = number(info.get('numberOfAnalystOpinions'), True)
        if target_count is not None:
            st.caption(f'Provider reports {target_count:g} price-target opinions; this can differ from rating counts.')
        st.caption(f'Target request checked: {timestamp(quote_fetched)}. '
                   'Target horizon and publication timestamp are not supplied here. Not a forecast by this app.')
    else:
        st.caption('Average analyst price target unavailable.')
    st.caption(f'Ratings request checked: {timestamp(analysts_fetched)}. '
               'Yahoo labels the rating snapshot “0m” (current period); an exact publication timestamp is not supplied.')

with st.expander('How to read this dashboard'):
    st.markdown('''**Daily change** = latest regular-session price − previous official close.

**Daily percentage change** = daily change ÷ previous official close × 100.
When the market is closed, this describes the last quoted session, not a new trading day.

**Consensus** is calculated from Yahoo’s current rating counts: Strong Buy = 1,
Buy = 2, Hold = 3, Sell = 4, Strong Sell = 5. The weighted mean is rounded to the
nearest category, with half-point ties toward the more bearish category.
This transparent classification may differ from Yahoo’s headline recommendation.
Missing categories are treated as unavailable, never as zero.

**Price target upside/downside** = (average target ÷ displayed price − 1) × 100.
Targets and analyst counts can be updated on different schedules.

**Timing:** request times indicate when this app checked the provider, not when
an analyst changed a rating. Quotes cache for 60 seconds, charts for 5 minutes,
and ratings for 1 hour. Refresh Data clears these caches (15-second click cooldown).
Market status uses the NASDAQ holiday/early-close calendar, not quote freshness.

**On iPhone:** open your deployed URL in Safari → Share → Add to Home Screen.
An internet connection is required. This is a browser app, not a native iOS app.''')

st.divider()
st.caption('SOURCE · Yahoo Finance via yfinance. Unofficial integration; data availability and delays vary. '
           'For a personal educational project. Analyst opinions are not guaranteed outcomes.')
st.markdown('[View NVDA on Yahoo Finance](https://finance.yahoo.com/quote/NVDA/)')

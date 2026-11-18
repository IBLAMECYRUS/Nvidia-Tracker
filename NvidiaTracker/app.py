"""NvidiaTracker — a small Python for Finance project. Run: streamlit run app.py"""
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

st.set_page_config(page_title='NvidiaTracker', page_icon='🟢', layout='centered')




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



def refresh_data():
    """A callback runs BEFORE the script, so the price above the button updates too."""
    last_click = st.session_state.get('last_refresh_click', 0)
    if time.time() - last_click >= 15:
        fetch_quote.clear()
        fetch_history.clear()
        fetch_analysts.clear()
        market_schedule.clear()
        st.session_state.last_refresh_click = time.time()
    else:
        st.session_state.refresh_message = 'Please wait 15 seconds between manual refreshes.'


def render_overview(info, quote_fetched, quote_error):
    st.markdown('<div id=overview class=page-title role=heading aria-level=2>Overview <span>01 / 03</span></div>', unsafe_allow_html=True)
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
    st.button('↻  Refresh Data', width='stretch', on_click=refresh_data, key='refresh_data')
    message = st.session_state.pop('refresh_message', None)
    if message:
        st.info(message)
    st.caption(delay_text + '.')
    if quote_error or price is None:
        st.warning(quote_error or 'The provider did not return a valid latest price. No estimated price is shown.')
    with st.expander('Quote details'):
        st.caption(status_detail)
        st.caption(f'Quote request checked: {timestamp(quote_fetched)}')
        if quote_time and (now_utc() - quote_time).total_seconds() > 900:
            st.caption('This is an older quote, not a live tick. Closed markets retain the last available regular-session price.')


def render_chart():
    st.markdown('<div id=price-graph class=page-title role=heading aria-level=2>Price graph <span>02 / 03</span></div>', unsafe_allow_html=True)
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
        fig.update_layout(height=265, margin=dict(l=0,r=8,t=12,b=0),
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
        st.caption(f'{date_label}: {chart_date}.')
        if label == '1 Day':
            st.caption('Most recent available regular session · 5-minute bars. Bar timestamps indicate interval starts.')
        elif label == '1 Week':
            st.caption('Last 5 trading sessions · 30-minute bars.')
        elif label == '5 Years':
            st.caption('Weekly observations; timestamps label the start of each weekly interval.')
    with st.expander('Chart details'):
        st.caption('Split-adjusted closing prices; dividends excluded. Intraday times are Eastern.')
        st.caption(f'History request checked: {timestamp(history_fetched)}')
        st.caption('The period return uses the first and last displayed observations, not the previous official close.')


def render_analysts(info, price, quote_fetched):
    st.markdown('<div id=analyst-consensus class=page-title role=heading aria-level=2>Analyst consensus <span>03 / 03</span></div>', unsafe_allow_html=True)
    with st.spinner('Checking analyst ratings…'):
        summary, analysts_fetched, analysts_error = fetch_analysts()
    if summary is None:
        st.info(analysts_error or 'Current analyst counts are unavailable. No consensus rating has been invented.')
    else:
        consensus_color = GREEN if summary['score'] < 2.5 else RED if summary['score'] >= 3.5 else '#B6BDA8'
        st.markdown(f"<div style='border:1px solid {consensus_color};background:#1c2b20;border-radius:60px;width:95px;height:95px;display:flex;align-items:center;justify-content:center;text-align:center;font-size:1.3rem;color:{consensus_color};margin:4px auto;'>{summary['label']}</div>", unsafe_allow_html=True)
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
        bars.update_layout(height=180, margin=dict(l=0,r=85,t=8,b=10),
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#BAC7BF'), xaxis=dict(visible=False, fixedrange=True),
                    yaxis=dict(autorange='reversed', fixedrange=True), bargap=.45, dragmode=False)
        st.plotly_chart(bars, width='stretch', config={'displayModeBar':False})
    target = number(info.get('targetMeanPrice'), True)
    if target:
        st.markdown(f'**Average target: {dollars(target)}**')
        _, upside = price_change(target, price)
        if upside is not None:
            st.caption(f'{upside:+.2f}% implied upside/downside versus the displayed quote.')
    else:
        st.caption('Average analyst price target unavailable.')
    with st.expander('Rating & target details'):
        target_count = number(info.get('numberOfAnalystOpinions'), True)
        if target and target_count is not None:
            st.caption(f'Provider reports {target_count:g} price-target opinions; this can differ from rating counts.')
        st.caption(f'Target request checked: {timestamp(quote_fetched)}. Target horizon and publication timestamp are not supplied here.')
        st.caption(f'Ratings request checked: {timestamp(analysts_fetched)}. Yahoo labels this snapshot “0m” (current period); an exact publication timestamp is not supplied.')
        st.caption('Consensus is calculated from current counts: Strong Buy=1, Buy=2, Hold=3, Sell=4, Strong Sell=5. The weighted mean is rounded to the nearest category; half-point ties use the more bearish category. Missing counts are never replaced with zero. Analyst opinions are not guaranteed outcomes.')


# A native horizontal Streamlit container keeps all widgets in Python.
# CSS gives each child one viewport width and snaps horizontal swipes to pages.
st.markdown("""<style>
.block-container {max-width:850px; padding:3.5rem 1rem 0.5rem;}
header[data-testid="stHeader"] {background:transparent;}
.brand {text-align:center;font-size:1.7rem !important;font-weight:650 !important;letter-spacing:-.04em;padding:0 !important;margin:0;line-height:1.2 !important;}
.brand span {color:#9bdf46;}
.tagline {text-align:center;color:#94a299;font-size:.78rem;margin:6px 0 0;}
.page-nav {display:flex;gap:8px;margin:0;}
.page-nav a {display:flex;align-items:center;justify-content:center;flex:1;min-height:44px;border:1px solid #2a382d;border-radius:12px;text-decoration:none;color:#d8e1d9;font-size:.85rem;background:#141a17;}
.page-nav a:hover,.page-nav a:focus-visible {border-color:#9bdf46;color:#9bdf46;outline-offset:2px;}
.page-title {scroll-margin-top:180px;font-size:1.12rem !important;padding:0 0 4px !important;margin:0 !important;font-weight:600 !important;display:flex;align-items:center;justify-content:space-between;}
.page-title span {font-size:.7rem;color:#94a299;letter-spacing:.1em;font-weight:400;}
.st-key-pages {height:calc(100svh - 250px) !important;max-height:calc(100svh - 250px) !important;min-height:0 !important;flex-shrink:0 !important;overflow-x:auto !important;overflow-y:hidden !important;scroll-snap-type:x mandatory;scroll-behavior:smooth;overscroll-behavior-x:contain;scrollbar-width:thin;scrollbar-color:#41513f #0c100d;flex-wrap:nowrap !important;}
.st-key-pages > [data-testid="stLayoutWrapper"] {flex:0 0 100% !important;width:100% !important;min-width:100% !important;height:100% !important;max-height:100% !important;min-height:0 !important;scroll-snap-align:start;scroll-snap-stop:always;}
.st-key-page_overview,.st-key-page_chart,.st-key-page_analysts {flex:0 0 100% !important;width:100% !important;min-width:100% !important;height:100% !important;max-height:100% !important;min-height:0 !important;gap:.5rem !important;overflow-y:auto !important;overflow-x:hidden !important;scroll-snap-align:start;scroll-snap-stop:always;padding:12px 12px 20px;border:1px solid #263329;border-radius:18px;box-sizing:border-box;scrollbar-width:thin;}
.eyebrow {color:#94a299;font-size:.72rem;letter-spacing:.13em;text-transform:uppercase;}
.hero {text-align:center;padding:24px 16px;background:linear-gradient(130deg,#1b251c,#111713 70%);border:1px solid #2a382d;border-radius:20px;margin:0;}
.company {font-size:1.05rem;font-weight:600;margin:10px 0 5px;}
.price {font-size:clamp(2.8rem,10vw,4.4rem);letter-spacing:-.055em;line-height:1.2;font-weight:350;}
.change {font-size:.95rem;margin-top:8px;font-weight:600;}
.small {font-size:.78rem;color:#a8b6ac;margin-top:14px;line-height:1.65;}
.badge {display:inline-block;padding:5px 10px;border:1px solid #36473a;border-radius:30px;font-size:.7rem;color:#c4d2c7;margin:4px 4px 0 0;}
.stats {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:0;}
.stat {background:#151b17;border:1px solid #29332c;border-radius:12px;padding:10px;}
.stat b {display:block;font-size:1.3rem;margin-top:4px;}
.stat span {color:#a8b6ac;font-size:.72rem;}
.st-key-refresh_data {margin-top:8px;}
div.stButton > button {min-height:46px;border-radius:12px;}
div[data-testid="stRadio"] label {min-height:44px;padding:4px 2px;}
.st-key-page_chart [data-testid="stPlotlyChart"] {touch-action:pan-x pan-y;}
.swipe-hint {text-align:center;color:#94a299;font-size:.72rem;margin:0;}
@media(max-width:600px){.block-container{padding:3.5rem .75rem .5rem;} .hero{padding:22px 10px;} .stat{padding:8px;} .page-nav a{font-size:.8rem;} .st-key-pages{height:calc(100svh - 250px);}}
@media(prefers-reduced-motion:reduce){.st-key-pages{scroll-behavior:auto;}}
</style>""", unsafe_allow_html=True)

st.markdown('<div class="brand" role="heading" aria-level="1">Nvidia<span>Tracker</span></div><p class="tagline">Your view of NVDA. Price, performance, perspective.</p>', unsafe_allow_html=True)
st.markdown('<nav class="page-nav" aria-label="Dashboard pages"><a href="#overview" target="_self">Overview</a><a href="#price-graph" target="_self">Price graph</a><a href="#analyst-consensus" target="_self">Analysts</a></nav>', unsafe_allow_html=True)

with st.spinner('Checking Yahoo Finance…'):
    info, quote_fetched, quote_error = fetch_quote()
price = number(info.get('regularMarketPrice'), True)

# Each page occupies the full row width; move sideways to reach the next page.
with st.container(horizontal=True, wrap=False, gap='medium', key='pages'):
    with st.container(key='page_overview'):
        render_overview(info, quote_fetched, quote_error)
    with st.container(key='page_chart'):
        render_chart()
    with st.container(key='page_analysts'):
        render_analysts(info, price, quote_fetched)
st.markdown('<p class="swipe-hint">Swipe sideways or choose a page above · Yahoo Finance via yfinance</p>', unsafe_allow_html=True)

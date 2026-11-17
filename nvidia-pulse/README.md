# NVIDIA Pulse

A mobile-first NVIDIA (NASDAQ: NVDA) dashboard built primarily with Python and Streamlit for a college Python for Finance project. Dark cards, a large centered price, an interactive chart, and a consensus badge take visual inspiration from the supplied stock-app screenshots. All displayed financial data comes from Yahoo Finance through yfinance. Screenshot prices are not embedded in the app.

## 1. Run locally

Use Python 3.12 (the tested version). Extract the ZIP and open a terminal **inside the nvidia-pulse folder**.

Windows:

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m streamlit run app.py
```

macOS/Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

Open http://localhost:8501 on the computer. Keep the terminal running. Stop the server with Ctrl+C. No API key is needed for this implementation.

### Open on an iPhone on the same Wi-Fi

Start Streamlit with `--server.address 0.0.0.0` appended to the command. Open the Network URL printed by Streamlit (for example `http://YOUR-COMPUTER-LAN-IP:8501`) in Safari. Use the computer's real local IP, not localhost on the phone. Allow port 8501 through the computer firewall on your trusted private network. The computer must remain awake and running. Do not expose this local server to the public internet by forwarding router ports; use hosting below instead.

## 2. Deploy using Streamlit Community Cloud

1. Create a GitHub repository and upload the **contents** of this project folder. Include `app.py`, `finance.py`, `requirements.txt`, and `.streamlit/config.toml`. Do not upload a virtual environment.
2. Sign in at https://share.streamlit.io and connect the GitHub account.
3. Select **Create app**, select the repository and branch, and set the entrypoint to `app.py`. If you uploaded the containing folder, use `nvidia-pulse/app.py` and keep its sibling files together.
4. Choose Python 3.12 in advanced settings if available, then deploy.
5. Open the resulting HTTPS URL in iPhone Safari. Tap **Share → Add to Home Screen**. The app remains a browser application and requires internet; it is not an offline/native iOS app.

This source package is ready to deploy, but no public hosted URL has been created as part of the delivery. Community Cloud requires your GitHub/Streamlit account. Yahoo may rate-limit cloud IP addresses; inspect deployment logs if data is unavailable and try again later. No data is fabricated when a provider request fails.

Official deployment guide: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app

## 3. Files

- `app.py`: data retrieval, caching, mobile layout, charts, and user interactions.
- `finance.py`: short, reusable functions for numbers, returns, ratings, price cleaning, and market-session classification.
- `.streamlit/config.toml`: dark theme and Streamlit configuration.
- `requirements.txt`: runtime dependencies.
- `tests/`: financial calculation and Streamlit UI tests using clearly synthetic fixtures; these fixtures never appear in the running app.
- `VALIDATION.md`: verification performed and remaining limits.

## 4. Features and data

### Quote

Uses Yahoo `regularMarketPrice`, `regularMarketPreviousClose`, and `regularMarketTime`. The displayed quote deliberately represents the **regular trading session**, excluding premarket and after-hours trades. The headline timestamp is the provider's quote timestamp. If a required field is missing, the app shows an unavailable state instead of estimating it from inconsistent data.

A separate request timestamp records when the app contacted Yahoo. Refreshing at night does not make the market quote new. The dashboard shows the provider-reported delay when supplied; otherwise it explicitly states that real-time status is not verified. A provider delay of zero does not guarantee delivery latency is zero.

NASDAQ market status is computed with `pandas_market_calendars`, including holidays and early closes. The daily schedule is cached; the open/closed comparison is recalculated on every page interaction. A page left idle must be refreshed to update its status. Status means whether the scheduled regular session is open now; it does not detect unscheduled halts or guarantee a fresh quote. Calendar rules depend on the installed library version.

### Historical chart

| Selection | Data requested | Observation interval |
|---|---|---|
| 1 Day | Most recent available session | 5 minutes |
| 1 Week | Last 5 trading sessions | 30 minutes |
| 1 Month | 1 month | Daily |
| 3 Months | 3 months | Daily |
| 1 Year | 1 year | Daily |
| 5 Years | 5 years | Weekly |

Charts use Yahoo's split-adjusted `Close` prices with `auto_adjust=False`; they are **not total-return charts** and do not include reinvested dividends. Python sorts observations, removes duplicate timestamps, and removes missing/nonpositive prices. Chart performance compares the first and last displayed observations, so the one-day chart return can differ from the headline change versus the prior official close. Linear segments avoid inventing price peaks. The price axis is explicitly scaled to the observed prices. With only one valid observation, the app displays a point and says a period return is not yet available. Tap on mobile or hover on desktop for values. Weekly timestamps label interval starts; daily timestamps identify trading dates rather than exact quote-update times.

### Analysts

Uses `get_recommendations_summary()` and only the `0m` (current period) row. Five separate provider categories are displayed. The three summary cards group Strong Buy with Buy, and Strong Sell with Sell. Missing counts, incomplete categories, or no current-period row produce an unavailable message, not zeros or stale substitutes.

The overall label is **calculated by this app from actual counts**:

```
score = (1*strongBuy + 2*buy + 3*hold + 4*sell + 5*strongSell) / total
```

| Weighted score | App label |
|---|---|
| 1.0 to less than 1.5 | Strong Buy |
| 1.5 to less than 2.5 | Buy |
| 2.5 to less than 3.5 | Hold |
| 3.5 to less than 4.5 | Sell |
| 4.5 to 5.0 | Strong Sell |

This is a transparent project method, not an assertion that Yahoo uses identical classification thresholds. Rating timestamps are not supplied by this endpoint: the UI labels the current reporting period and retrieval timestamp separately. The optional average target uses `targetMeanPrice`; `numberOfAnalystOpinions` relates to price targets and may differ from the rating total. The API does not supply the exact target publication time or horizon here, so the app does not invent either.

### Financial calculations

```
daily dollar change = latest regular-session price - previous official close
daily percent change = daily dollar change / previous official close * 100
chart period percent = (last displayed price / first displayed price - 1) * 100
target upside/downside = (average analyst target / displayed quote - 1) * 100
```

Invalid or zero denominators return unavailable instead of crashing. Positive changes are green, negative changes red, and unchanged prices muted gray. Targets summarize opinions rather than guaranteed outcomes.

## 5. Refresh and reliability

Quote requests cache for 60 seconds; charts for 300 seconds; analyst ratings for 3,600 seconds. Selecting a chart period loads its own cached history. **Refresh Data** clears all financial caches and fetches the currently selected history, quote/target fields, and ratings again. Other chart periods load fresh when selected. A 15-second per-session cooldown limits repeat clicks. Caches are shared by Streamlit's server, so a manual refresh invalidates the same caches for other viewers too.

Each data section handles failure independently. An unavailable analyst endpoint does not remove a working price chart. Nothing is filled with fake data or screenshot figures. There is no automatic retry loop, database, authentication, brokerage connection, or trade execution.

## 6. Tests

After installing requirements, run from the project directory:

```bash
python -m unittest discover -s tests -v
```

The suite checks positive/negative/zero returns, invalid denominators, consensus aggregation, missing/old ratings, history cleanup, all six chart period interactions, cache reuse, refresh and click cooldown, chart-axis scaling, date labels, holiday and early-close boundaries, and independent provider failures. Test fixtures are isolated to `tests/` and are not used as an app fallback.

## 7. How to explain this project to a professor

1. `yfinance` retrieves real data; cached functions reduce repeat network requests.
2. Pandas stores historical observations in a DataFrame and cleans them.
3. Simple arithmetic calculates daily returns, period returns, and target upside.
4. Rating counts produce a weighted average with an explicitly stated mapping.
5. Plotly displays interactive price and rating charts; Streamlit builds the browser interface.
6. Error handling and accurate timestamp labels prevent misleading output.

## Sources and limitations

- Yahoo NVDA quote: https://finance.yahoo.com/quote/NVDA/
- yfinance documentation: https://ranaroussi.github.io/yfinance/
- Analyst data API: https://ranaroussi.github.io/yfinance/reference/yfinance.analysis.html
- Streamlit documentation: https://docs.streamlit.io/
- NASDAQ calendar library: https://pandas-market-calendars.readthedocs.io/

`yfinance` is an unofficial open-source interface, not a Yahoo-endorsed paid market feed. Review Yahoo's terms and yfinance's personal-use guidance before any broader/commercial distribution. This project is intended for personal educational use. Availability, delay, and analyst coverage depend on the provider.

## Review corrections

The reviewed version corrects price-chart axis scaling, removes misleading midnight times from daily-bar labels, normalizes intraday labels to Eastern time, increases mobile tap targets, keeps the header clear of the toolbar, and shows a visible point when a series contains only one observation. It also validates malformed provider responses. The test suite now contains 19 tests.

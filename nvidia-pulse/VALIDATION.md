# NVIDIA Pulse — review and verification

Reviewed on November 17, 2026. Python 3.12 was used with the pinned dependencies in requirements.txt.

## Corrections made

- Fixed conflicting Plotly axis settings: explicit price bounds now disable autorange, so the area fill does not force the price axis down to zero.
- Daily chart timestamps now identify trading dates, rather than implying that the closing price was observed at midnight. Weekly observations identify week starts. Intraday tooltips explicitly use Eastern time independent of browser timezone.
- Increased radio-control tap targets to at least 44 pixels tall and moved the mobile header below the Streamlit toolbar.
- A one-observation chart displays a visible marker and explains that a period return cannot yet be calculated.
- Added validation for malformed quote responses, invalid history dates, and non-finite calculations.
- Cached only the exchange schedule, with the open/closed comparison recalculated on page interaction. Price-target retrieval time is now explicitly displayed.

## Automated checks

19 tests pass. They cover:

- Gain, loss, unchanged prices, actual decimal rounding, invalid denominators, and overflow.
- All five rating categories, category threshold ties, grouped totals, rejection of missing/old/invalid ratings, and use of only the current reporting period.
- Sorting/deduplication/cleaning of price history.
- Regular-session opening and closing boundaries, a weekend, Thanksgiving, and the early close the day after Thanksgiving.
- All six chart selections and their provider query arguments.
- Cache reuse, manual refresh fetching new values, and the click cooldown.
- Price-axis bounds, tooltip date formatting, negative/flat/single-observation charts.
- Complete provider outage, analyst-only outage, and missing quote fields.

A new isolated virtual environment installed every dependency from requirements.txt successfully. `pip check` reported no broken requirements. This confirms the package works without relying on the original workspace's installed libraries.

## Actual provider checks

Yahoo Finance returned a regular-session NVDA quote, a previous close, a quote timestamp, a mean target, and current analyst-count data. Each chart request succeeded:

| Period | Valid observations returned |
|---|---:|
| 1 Day | 78 |
| 1 Week | 65 |
| 1 Month | 22 |
| 3 Months | 65 |
| 1 Year | 251 |
| 5 Years | 262 |

These are observations from the verification run, not fixed expected counts. Future counts will vary with the trading calendar. No fixture data is displayed by the app.

## Browser checks

The real Streamlit application rendered in Chrome. The price chart, hover values, analyst badge, five rating bars, grouped counts, price target, and period selector were inspected with actual Yahoo data. The one-day selector changed the chart and its date labels correctly.

Phone-width checks used 375-, 390-, and 430-CSS-pixel embedded browser viewports. At each width, the document width matched the viewport with no horizontal overflow; both chart containers fit. The 390-pixel screenshots confirmed readable chart/analyst panels. This is a responsive-layout check, not a physical-device test or Safari-engine emulation.

## Remaining limits

- No physical iPhone/Safari test has been completed.
- No Streamlit Community Cloud production deployment has been performed. Instructions are included in README.md.
- Provider availability, delays, and coverage can change. Successful requests during verification do not guarantee future availability.
- Market status reflects scheduled regular sessions and updates on page interactions; it does not detect unscheduled trading halts or update an idle page automatically.

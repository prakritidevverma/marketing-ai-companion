# Market Observatory (work in progress)

Nightly data collector and analytics for NIFTY: FPI/DII flows, participant-wise
derivatives positioning, option-chain volatility (ATM IV, skew, term structure),
cross-asset markets and news.

**Status:** early scaffold. Written so far:

- `observatory/config.py` – settings, market tickers, news feeds
- `observatory/store.py` – Parquet storage with key-based upserts
- `observatory/sources/http.py` – browser-like session with retries for NSE
- `observatory/sources/nse.py` – parsers/fetchers for participant-wise OI,
  F&O bhavcopy (UDiFF and legacy formats) and FII/DII provisional flows

Scope (full dashboard vs collector + journal) is pending a decision; see the
conversation notes. Not yet tested against live NSE data.

"""Settings in one place. Override the data directory with OBS_DATA_DIR."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class MarketTicker:
    key: str      # column name used everywhere downstream
    symbol: str   # Yahoo Finance symbol
    label: str    # human label for charts


# Yahoo Finance symbols for the cross-asset layer.
MARKET_TICKERS: tuple[MarketTicker, ...] = (
    MarketTicker("nifty", "^NSEI", "NIFTY 50"),
    MarketTicker("usdinr", "INR=X", "USD/INR"),
    MarketTicker("india_vix", "^INDIAVIX", "India VIX"),
    MarketTicker("msci_em", "EEM", "MSCI EM (EEM, USD)"),
    MarketTicker("korea", "EWY", "Korea (EWY, USD)"),
    MarketTicker("taiwan", "EWT", "Taiwan (EWT, USD)"),
    MarketTicker("brent", "BZ=F", "Brent crude"),
    MarketTicker("dxy", "DX-Y.NYB", "US Dollar Index"),
    MarketTicker("us10y", "^TNX", "US 10Y yield"),
)

# Free RSS feeds, primary sources first. Edit freely; a feed that fails is skipped.
NEWS_FEEDS: dict[str, str] = {
    "RBI press releases": "https://www.rbi.org.in/pressreleases_rss.xml",
    "SEBI": "https://www.sebi.gov.in/sebirss.xml",
    "Federal Reserve": "https://www.federalreserve.gov/feeds/press_all.xml",
    "Business Standard Markets": "https://www.business-standard.com/rss/markets-106.rss",
    "Mint Markets": "https://www.livemint.com/rss/markets",
    "ET Markets": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
}


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("OBS_DATA_DIR", "data")))
    reports_dir: Path = field(default_factory=lambda: Path(os.environ.get("OBS_REPORTS_DIR", "reports")))
    underlying: str = "NIFTY"
    risk_free_rate: float = 0.065          # used only to discount in Black-76; small effect
    min_days_front: int = 2                # skip expiries closer than this (expiry-day noise)
    constant_maturity_days: int = 30       # the "monthly" IV reference
    min_option_price: float = 0.5          # ignore sub-0.5 point premiums (tick noise)
    flow_window: int = 20                  # rolling sum window for FPI/DII flows
    zscore_lookback: int = 250             # one trading year
    zscore_min_obs: int = 60
    percentile_lookback: int = 500         # two trading years for positioning extremes
    ledger_entry_days: int = 7             # expiry ledger: enter N calendar days before expiry
    request_delay_s: float = 0.4           # be polite to NSE
    default_backfill_days: int = 365

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def chain_dir(self) -> Path:
        return self.data_dir / "raw" / "fo_chain"

    @property
    def derived_dir(self) -> Path:
        return self.data_dir / "derived"

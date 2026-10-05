"""Parquet-backed storage with key-based upserts."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import Settings

# dataset name -> (relative path, primary key columns)
DATASETS: dict[str, tuple[str, list[str]]] = {
    "participant_oi": ("raw/participant_oi.parquet", ["date", "client_type"]),
    "flows": ("raw/flows.parquet", ["date", "source"]),
    "markets": ("raw/markets.parquet", ["date"]),
    "news": ("raw/news.parquet", ["link"]),
    "vol_by_expiry": ("derived/vol_by_expiry.parquet", ["date", "expiry"]),
    "vol_daily": ("derived/vol_daily.parquet", ["date"]),
    "expiry_ledger": ("derived/expiry_ledger.parquet", ["expiry"]),
}


class Store:
    def __init__(self, settings: Settings):
        self.settings = settings

    def path(self, name: str) -> Path:
        rel, _ = DATASETS[name]
        return self.settings.data_dir / rel

    def read(self, name: str) -> pd.DataFrame:
        p = self.path(name)
        if not p.exists():
            return pd.DataFrame()
        return pd.read_parquet(p)

    def write(self, name: str, df: pd.DataFrame) -> None:
        p = self.path(name)
        p.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(p, index=False)

    def upsert(self, name: str, new: pd.DataFrame) -> pd.DataFrame:
        """Merge `new` into the dataset; rows with the same key are replaced by `new`."""
        if new is None or new.empty:
            return self.read(name)
        _, keys = DATASETS[name]
        old = self.read(name)
        merged = new if old.empty else pd.concat([old, new], ignore_index=True)
        merged = merged.drop_duplicates(subset=keys, keep="last")
        sort_cols = [k for k in keys if k in merged.columns]
        merged = merged.sort_values(sort_cols).reset_index(drop=True)
        self.write(name, merged)
        return merged

    # Option-chain snapshots are cached one file per trading day.
    def chain_path(self, day: pd.Timestamp) -> Path:
        return self.settings.chain_dir / f"{day:%Y-%m-%d}.parquet"

    def has_chain(self, day: pd.Timestamp) -> bool:
        return self.chain_path(day).exists()

    def write_chain(self, day: pd.Timestamp, df: pd.DataFrame) -> None:
        p = self.chain_path(day)
        p.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(p, index=False)

    def chain_days(self) -> list[pd.Timestamp]:
        d = self.settings.chain_dir
        if not d.exists():
            return []
        return sorted(pd.Timestamp(f.stem) for f in d.glob("*.parquet"))

    def read_chains(self, days: list[pd.Timestamp] | None = None) -> pd.DataFrame:
        days = self.chain_days() if days is None else days
        frames = [pd.read_parquet(self.chain_path(d)) for d in days if self.has_chain(d)]
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

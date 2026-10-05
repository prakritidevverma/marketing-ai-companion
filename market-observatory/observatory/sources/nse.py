"""NSE end-of-day files: participant-wise OI, F&O bhavcopy and FII/DII provisional flows.

All parsers take raw bytes/text so they can be tested without the network.
"""

from __future__ import annotations

import io
import logging
import re
import zipfile

import numpy as np
import pandas as pd

from .http import NotFound, NSESession

log = logging.getLogger(__name__)

ARCHIVE_HOSTS = ("https://nsearchives.nseindia.com", "https://archives.nseindia.com")
UDIFF_START = pd.Timestamp("2024-07-08")  # NSE switched F&O bhavcopy to the UDiFF format

CHAIN_COLUMNS = [
    "date", "instrument", "expiry", "strike", "opt_type",
    "close", "settle", "oi", "chg_oi", "volume", "underlying",
]

PARTICIPANT_COLUMNS = {
    "client type": "client_type",
    "future index long": "fut_idx_long",
    "future index short": "fut_idx_short",
    "future stock long": "fut_stk_long",
    "future stock short": "fut_stk_short",
    "option index call long": "opt_idx_call_long",
    "option index put long": "opt_idx_put_long",
    "option index call short": "opt_idx_call_short",
    "option index put short": "opt_idx_put_short",
    "option stock call long": "opt_stk_call_long",
    "option stock put long": "opt_stk_put_long",
    "option stock call short": "opt_stk_call_short",
    "option stock put short": "opt_stk_put_short",
    "total long contracts": "total_long",
    "total short contracts": "total_short",
}


def _to_number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.replace(",", "").str.strip(), errors="coerce")


# ---------------------------------------------------------------- participant OI

def participant_oi_urls(day: pd.Timestamp) -> list[str]:
    return [f"{h}/content/nsccl/fao_participant_oi_{day:%d%m%Y}.csv" for h in ARCHIVE_HOSTS]


def parse_participant_oi(text: str, day: pd.Timestamp) -> pd.DataFrame:
    """Parse NSE's fao_participant_oi CSV (a title line, then a header starting 'Client Type')."""
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.strip().strip('"').lower().startswith("client type")), None)
    if start is None:
        raise ValueError("participant OI file has no 'Client Type' header")
    df = pd.read_csv(io.StringIO("\n".join(lines[start:])), dtype=str)
    df.columns = [re.sub(r"\s+", " ", str(c)).strip().lower() for c in df.columns]
    df = df.rename(columns=PARTICIPANT_COLUMNS)
    missing = [c for c in PARTICIPANT_COLUMNS.values() if c not in df.columns]
    if missing:
        raise ValueError(f"participant OI file is missing columns: {missing}")
    df = df[list(PARTICIPANT_COLUMNS.values())].copy()
    df["client_type"] = df["client_type"].astype(str).str.strip().str.upper()
    df = df[df["client_type"].isin(["CLIENT", "DII", "FII", "PRO", "TOTAL"])]
    for col in df.columns:
        if col != "client_type":
            df[col] = _to_number(df[col])
    df.insert(0, "date", pd.Timestamp(day).normalize())
    return df.reset_index(drop=True)


def fetch_participant_oi(session: NSESession, day: pd.Timestamp) -> pd.DataFrame:
    last_exc: Exception | None = None
    for url in participant_oi_urls(day):
        try:
            return parse_participant_oi(session.get(url).text, day)
        except NotFound as exc:
            last_exc = exc
    raise NotFound(str(last_exc))


# ---------------------------------------------------------------- F&O bhavcopy

def bhavcopy_urls(day: pd.Timestamp) -> list[tuple[str, str]]:
    """Candidate (format, url) pairs, most likely first."""
    mon = day.strftime("%b").upper()
    udiff = [("udiff", f"{h}/content/fo/BhavCopy_NSE_FO_0_0_0_{day:%Y%m%d}_F_0000.csv.zip") for h in ARCHIVE_HOSTS]
    legacy = [
        ("legacy", f"{h}/content/historical/DERIVATIVES/{day:%Y}/{mon}/fo{day:%d}{mon}{day:%Y}bhav.csv.zip")
        for h in ARCHIVE_HOSTS
    ]
    return udiff + legacy if day >= UDIFF_START else legacy + udiff


def _read_zipped_csv(content: bytes) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
        with zf.open(name) as fh:
            return pd.read_csv(fh, dtype=str)


def parse_udiff_bhavcopy(raw: pd.DataFrame, underlying: str = "NIFTY") -> pd.DataFrame:
    raw = raw.rename(columns=lambda c: str(c).strip())
    sym = raw["TckrSymb"].str.strip()
    kind = raw["FinInstrmTp"].str.strip()
    df = raw[(sym == underlying) & kind.isin(["IDO", "IDF"])].copy()
    out = pd.DataFrame({
        "date": pd.to_datetime(df["TradDt"].str.strip()),
        "instrument": np.where(kind.loc[df.index] == "IDO", "OPT", "FUT"),
        "expiry": pd.to_datetime(df["XpryDt"].str.strip()),
        "strike": _to_number(df["StrkPric"]),
        "opt_type": df["OptnTp"].fillna("").str.strip().replace("", None),
        "close": _to_number(df["ClsPric"]),
        "settle": _to_number(df["SttlmPric"]),
        "oi": _to_number(df["OpnIntrst"]),
        "chg_oi": _to_number(df["ChngInOpnIntrst"]),
        "volume": _to_number(df["TtlTradgVol"]),
        "underlying": _to_number(df["UndrlygPric"]) if "UndrlygPric" in df else np.nan,
    })
    return _finish_chain(out)


def parse_legacy_bhavcopy(raw: pd.DataFrame, underlying: str = "NIFTY") -> pd.DataFrame:
    raw = raw.rename(columns=lambda c: str(c).strip())
    sym = raw["SYMBOL"].str.strip()
    inst = raw["INSTRUMENT"].str.strip()
    df = raw[(sym == underlying) & inst.isin(["OPTIDX", "FUTIDX"])].copy()
    opt = df["OPTION_TYP"].str.strip()
    out = pd.DataFrame({
        "date": pd.to_datetime(df["TIMESTAMP"].str.strip(), format="%d-%b-%Y"),
        "instrument": np.where(inst.loc[df.index] == "OPTIDX", "OPT", "FUT"),
        "expiry": pd.to_datetime(df["EXPIRY_DT"].str.strip(), format="%d-%b-%Y"),
        "strike": _to_number(df["STRIKE_PR"]),
        "opt_type": opt.where(opt.isin(["CE", "PE"]), None),
        "close": _to_number(df["CLOSE"]),
        "settle": _to_number(df["SETTLE_PR"]),
        "oi": _to_number(df["OPEN_INT"]),
        "chg_oi": _to_number(df["CHG_IN_OI"]),
        "volume": _to_number(df["CONTRACTS"]),
        "underlying": np.nan,
    })
    return _finish_chain(out)


def _finish_chain(out: pd.DataFrame) -> pd.DataFrame:
    out.loc[out["instrument"] == "FUT", ["strike", "opt_type"]] = [np.nan, None]
    out["underlying"] = out["underlying"].astype(float)
    return out[CHAIN_COLUMNS].reset_index(drop=True)


def fetch_bhavcopy(session: NSESession, day: pd.Timestamp, underlying: str = "NIFTY") -> pd.DataFrame:
    for fmt, url in bhavcopy_urls(day):
        try:
            raw = _read_zipped_csv(session.get(url).content)
        except NotFound:
            continue
        parser = parse_udiff_bhavcopy if fmt == "udiff" else parse_legacy_bhavcopy
        return parser(raw, underlying)
    raise NotFound(f"no F&O bhavcopy for {day:%Y-%m-%d}")


# ---------------------------------------------------------------- FII/DII provisional

def parse_fiidii_json(payload: list[dict]) -> pd.DataFrame:
    """Parse NSE's /api/fiidiiTradeReact response (latest trading day only)."""
    rows: dict[pd.Timestamp, dict] = {}
    for item in payload:
        cat = str(item.get("category", "")).upper()
        who = "fii" if ("FII" in cat or "FPI" in cat) else "dii" if "DII" in cat else None
        if who is None:
            continue
        day = pd.to_datetime(item["date"], format="%d-%b-%Y")
        row = rows.setdefault(day, {"date": day, "source": "nse_provisional"})
        for key, col in (("buyValue", "buy"), ("sellValue", "sell"), ("netValue", "net")):
            row[f"{who}_{col}"] = float(str(item.get(key, "nan")).replace(",", ""))
    return pd.DataFrame(list(rows.values()))


def fetch_fiidii(session: NSESession) -> pd.DataFrame:
    return parse_fiidii_json(session.api("/api/fiidiiTradeReact").json())

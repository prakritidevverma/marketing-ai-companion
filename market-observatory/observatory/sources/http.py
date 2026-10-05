"""HTTP session that behaves like a browser, with retries and a polite delay.

NSE serves archive files to browser-like clients, but its JSON API also needs the
cookies set by the home page, so `NSESession.prime()` visits it first.
"""

from __future__ import annotations

import logging
import time

import requests

log = logging.getLogger(__name__)

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}


class NotFound(Exception):
    """The file does not exist (holiday, weekend, or not yet published)."""


class PoliteSession:
    def __init__(self, delay_s: float = 0.4, retries: int = 3, timeout_s: float = 30.0):
        self.session = requests.Session()
        self.session.headers.update(BROWSER_HEADERS)
        self.delay_s = delay_s
        self.retries = retries
        self.timeout_s = timeout_s
        self._last = 0.0

    def _wait(self) -> None:
        gap = time.monotonic() - self._last
        if gap < self.delay_s:
            time.sleep(self.delay_s - gap)
        self._last = time.monotonic()

    def get(self, url: str, **kwargs) -> requests.Response:
        backoff = 2.0
        for attempt in range(1, self.retries + 1):
            self._wait()
            try:
                resp = self.session.get(url, timeout=self.timeout_s, **kwargs)
            except requests.RequestException as exc:
                if attempt == self.retries:
                    raise
                log.debug("GET %s failed (%s), retrying", url, exc)
                time.sleep(backoff)
                backoff *= 2
                continue
            if resp.status_code == 404:
                raise NotFound(url)
            if resp.status_code in (401, 403, 429) or resp.status_code >= 500:
                if attempt == self.retries:
                    resp.raise_for_status()
                log.debug("GET %s -> %s, retrying", url, resp.status_code)
                self.on_denied()
                time.sleep(backoff)
                backoff *= 2
                continue
            resp.raise_for_status()
            return resp
        raise RuntimeError("unreachable")

    def on_denied(self) -> None:
        """Hook for subclasses that can refresh cookies."""


class NSESession(PoliteSession):
    HOME = "https://www.nseindia.com/"

    def __init__(self, delay_s: float = 0.4):
        super().__init__(delay_s=delay_s)
        self._primed = False

    def prime(self) -> None:
        if self._primed:
            return
        try:
            self._wait()
            self.session.get(self.HOME, timeout=self.timeout_s)
            self._primed = True
        except requests.RequestException as exc:
            log.warning("Could not prime NSE cookies: %s", exc)

    def on_denied(self) -> None:
        self._primed = False
        self.prime()

    def api(self, path: str) -> requests.Response:
        self.prime()
        return self.get(
            f"https://www.nseindia.com{path}",
            headers={"Referer": self.HOME, "Accept": "application/json"},
        )

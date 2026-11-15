"""HTTP-Hilfen mit Wiederholungen."""
from __future__ import annotations

import time

import requests

_session = requests.Session()
_session.headers["User-Agent"] = "wingbrief/0.1 (+https://github.com/fabianboesiger/wingbrief)"


def get(url: str, *, byte_range: tuple[int, int] | None = None, timeout: int = 120,
        retries: int = 4, **kw) -> requests.Response:
    headers = kw.pop("headers", {})
    if byte_range:
        headers["Range"] = f"bytes={byte_range[0]}-{byte_range[1]}"
    for attempt in range(retries):
        try:
            r = _session.get(url, headers=headers, timeout=timeout, **kw)
            r.raise_for_status()
            if byte_range and r.status_code != 206:
                raise IOError(f"Range nicht unterstützt: {url}")
            return r
        except (requests.RequestException, IOError):
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
    raise AssertionError


def post_json(url: str, payload: dict, timeout: int = 60, retries: int = 4) -> dict:
    for attempt in range(retries):
        try:
            r = _session.post(url, json=payload, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
    raise AssertionError

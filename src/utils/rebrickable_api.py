"""Shared helpers for Rebrickable API access.

Credentials are resolved via ``utils.common_functions.load_rebrickable_environment``,
which loads a ``.env`` file (ignored by Git) and exports
``REBRICKABLE_API_KEY`` for the current process.
This module keeps network-handling, pagination and error-handling logic in
one place so loaders and other scripts can stay concise.
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, Iterator, Optional, Tuple

import requests

from utils.common_functions import load_rebrickable_environment as _load_env

RB_API_BASE = "https://rebrickable.com/api/v3/lego"
DEFAULT_TIMEOUT = 30  # seconds
RETRY_STATUS = {429, 502, 503, 504}  # include rate‑limit 429

# --------------------------------------------------------------------------- core helpers

def _api_key() -> str:
    """
    Return the Rebrickable API key.

    Priority:
    1. Environment variable ``REBRICKABLE_API_KEY`` (already loaded by your
       shell or by ``common_functions.load_rebrickable_environment``).
    2. Fall back to calling ``load_rebrickable_environment()`` which reads the
       .env file and sets ``REBRICKABLE_API_KEY`` for this process.
    """
    key = os.getenv("REBRICKABLE_API_KEY")
    if key:
        return key

    # Load from .env via shared helper (also exits with a clear error if missing)
    key, *_ = _load_env()
    return key


def _headers() -> Dict[str, str]:
    return {"Authorization": f"key {_api_key()}"}


def get_json(endpoint: str, *, params: Optional[Dict[str, Any]] = None, timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """GET *endpoint* (relative to RB_API_BASE) and return decoded JSON.

    Retries once on the usual transient 50x errors.
    """
    url = endpoint if endpoint.startswith("http") else f"{RB_API_BASE}{endpoint}"
    for attempt in (1, 2):
        resp = requests.get(url, headers=_headers(), params=params, timeout=timeout)
        # If we hit Rebrickable's rate limit, sleep per Retry‑After header (or 5 s) then retry once
        if resp.status_code == 429 and attempt == 1:
            delay = int(resp.headers.get("Retry-After", "5"))
            time.sleep(delay)
            continue
        if resp.status_code in RETRY_STATUS and attempt == 1:
            time.sleep(1)
            continue
        resp.raise_for_status()
        return resp.json()
    raise AssertionError("Unreachable")

# --------------------------------------------------------------------------- pagination helpers

def paginate(endpoint: str, *, params: Optional[Dict[str, Any]] = None, timeout: int = DEFAULT_TIMEOUT) -> Iterator[Dict[str, Any]]:
    """Yield all results across paginated endpoints.

    Example::

        from utils.rebrickable_api import paginate
        for color in paginate("/colors/", params={"page_size": 1000}):
            ...
    """
    url = f"{RB_API_BASE}{endpoint}" if not endpoint.startswith("http") else endpoint
    while url:
        data = get_json(url, params=params, timeout=timeout)
        yield from data.get("results", [])
        url = data.get("next")
        params = None  # only send params on first request

# --------------------------------------------------------------------------- batch helpers

def bulk_parts_by_bricklink(bricklink_ids: list[str | int]) -> Dict[str, Tuple[str, str]]:
    """Return mapping alias → (design_id, name) for <=50 BrickLink ids.

    Works best under Rebrickable's rate‑limit; hard max is 100."""
    assert len(bricklink_ids) <= 50, "Pass at most 50 ids per call to avoid 429s"
    ids_param = ",".join(map(str, bricklink_ids))
    data = get_json(
        "/parts/",
        params={"bricklink_id__in": ids_param},
    )
    mapping: Dict[str, Tuple[str, str]] = {}
    for p in data.get("results", []):
        design_id = p["part_num"]
        name = p["name"]
        for bl in p["external_ids"].get("BrickLink", []):
            mapping[str(bl)] = (design_id, name)
    return mapping
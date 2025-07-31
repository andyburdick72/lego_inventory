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
import random
from typing import Any, Dict, Iterator, Optional, Tuple

import requests

from utils.common_functions import load_rebrickable_environment as _load_env

RB_API_BASE = "https://rebrickable.com/api/v3/lego"
DEFAULT_TIMEOUT = 30  # seconds
MAX_RETRIES = 5      # total attempts for transient errors
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

    Retries the usual transient errors (429, 502, 503, 504) **up to MAX_RETRIES**
    using exponential back‑off (1 s, 2 s, 4 s, …) plus a small random jitter.
    """
    url = endpoint if endpoint.startswith("http") else f"{RB_API_BASE}{endpoint}"

    for attempt in range(1, MAX_RETRIES + 1):
        resp = requests.get(url, headers=_headers(), params=params, timeout=timeout)

        # --- Successful response ---
        if resp.status_code < 400:
            return resp.json()

        # --- Retryable responses ---
        if resp.status_code in RETRY_STATUS and attempt < MAX_RETRIES:
            # Rate‑limit 429 honour explicit Retry‑After header, otherwise
            # exponential back‑off: 1s, 2s, 4s, 8s… plus jitter
            if resp.status_code == 429:
                delay = int(resp.headers.get("Retry-After", "5"))
            else:
                delay = 2 ** (attempt - 1)
            delay += random.uniform(0, 0.5)
            time.sleep(delay)
            continue

        # --- Non‑retryable or final failure ---
        resp.raise_for_status()

    raise RuntimeError("Unreachable – retries exhausted")

def _single_part_name(part_num: str) -> Optional[str]:
    """Return the canonical name for *part_num* or None if 404."""
    try:
        data = get_json(f"/parts/{part_num}/")
        return data["name"]
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return None
        raise

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

def bulk_parts(design_ids: list[str]) -> Dict[str, str]:
    """
    Return a mapping {design_id -> proper name} for ≤100 Rebrickable design‑IDs.

    The Rebrickable parts endpoint accepts up to 100 comma‑separated part
    numbers at a time.  Any unknown IDs are silently ignored so callers can
    pass raw lists without pre‑validation.
    """
    assert len(design_ids) <= 100, "Pass at most 100 ids per call (API hard limit)"
    ids_param = ",".join(design_ids)
    try:
        data = get_json(
            "/parts/",
            params={"part_nums": ids_param},
        )
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code in RETRY_STATUS:
            mapping: Dict[str, str] = {}
            for pid in design_ids:
                name = _single_part_name(pid)
                if name:
                    mapping[pid] = name
            return mapping
        else:
            raise
    mapping: Dict[str, str] = {}
    for part in data.get("results", []):
        mapping[part["part_num"]] = part["name"]
    return mapping
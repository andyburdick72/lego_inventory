"""Shared helpers for Rebrickable API access.

Credentials are resolved via centralized settings:
    from app.settings import get_settings

This module keeps network-handling, pagination and error-handling logic in
one place so loaders and other scripts can stay concise.
"""

from __future__ import annotations

import random
import time
from collections.abc import Iterator
from typing import Any

import requests

from app.errors import AppError, ExternalServiceError, RateLimitError, ValidationError
from app.settings import get_settings

RB_API_BASE = "https://rebrickable.com/api/v3/lego"
DEFAULT_TIMEOUT = 30  # seconds
MAX_RETRIES = 5  # total attempts for transient errors
RETRY_STATUS = {429, 502, 503, 504}  # include rate‑limit 429

# --------------------------------------------------------------------------- core helpers


def _api_key() -> str:
    """
    Return the Rebrickable API key from centralized settings, raising a clear error if missing.
    """
    key = get_settings().rebrickable_api_key
    if not key:
        raise AppError("Missing APP_REBRICKABLE_API_KEY in data/.env or environment")
    return key


def _headers() -> dict[str, str]:
    return {"Authorization": f"key {_api_key()}"}


def get_json(
    endpoint: str, *, params: dict[str, Any] | None = None, timeout: int = DEFAULT_TIMEOUT
) -> dict[str, Any]:
    """GET *endpoint* (relative to RB_API_BASE) and return decoded JSON.

    Retries transient errors (timeouts, connection issues, 429, 502, 503, 504) up to MAX_RETRIES
    with exponential backoff and jitter, and maps final failures into the app error taxonomy.
    """
    url = endpoint if endpoint.startswith("http") else f"{RB_API_BASE}{endpoint}"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, headers=_headers(), params=params, timeout=timeout)
        except requests.Timeout as e:
            if attempt < MAX_RETRIES:
                delay = 2 ** (attempt - 1) + random.uniform(0, 0.5)
                time.sleep(delay)
                continue
            raise ExternalServiceError("Rebrickable timeout") from e
        except requests.ConnectionError as e:
            if attempt < MAX_RETRIES:
                delay = 2 ** (attempt - 1) + random.uniform(0, 0.5)
                time.sleep(delay)
                continue
            raise ExternalServiceError("Rebrickable connection error") from e

        # --- Successful response ---
        if resp.status_code < 400:
            return resp.json()

        # --- Retryable responses ---
        if resp.status_code in RETRY_STATUS and attempt < MAX_RETRIES:
            if resp.status_code == 429:
                delay = int(resp.headers.get("Retry-After", "5"))
            else:
                delay = 2 ** (attempt - 1)
            delay += random.uniform(0, 0.5)
            time.sleep(delay)
            continue

        # --- Map final failure to taxonomy ---
        # 429: explicit rate limit
        if resp.status_code == 429:
            raise RateLimitError(
                "Rebrickable rate limit", details={"retry_after": resp.headers.get("Retry-After")}
            )

        # 4xx: treat as validation-ish errors; include upstream body when possible
        if 400 <= resp.status_code < 500:
            try:
                payload = resp.json()
            except Exception:
                payload = {"text": resp.text}
            details = {"status": resp.status_code, **({"payload": payload} if payload else {})}
            raise ValidationError(f"Rebrickable 4xx ({resp.status_code})", details=details)

        # 5xx: upstream failure
        if resp.status_code >= 500:
            raise ExternalServiceError(
                "Rebrickable upstream error",
                details={"status": resp.status_code, "text": resp.text[:500]},
            )

    # Defensive: loop always returns or raises above
    raise ExternalServiceError("Rebrickable request retries exhausted")


def _single_part_name(part_num: str) -> str | None:
    """Return the canonical name for *part_num* or None if 404."""
    try:
        data = get_json(f"/parts/{part_num}/")
        return data["name"]
    except ValidationError as exc:  # rebrickable 4xx
        details = getattr(exc, "details", {}) or {}
        if isinstance(details, dict) and details.get("status") == 404:
            return None
        return None


# --------------------------------------------------------------------------- pagination helpers


def paginate(
    endpoint: str, *, params: dict[str, Any] | None = None, timeout: int = DEFAULT_TIMEOUT
) -> Iterator[dict[str, Any]]:
    """Yield all results across paginated endpoints.

    Example::

        from core.services.rebrickable_api import paginate
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


def bulk_parts_by_bricklink(bricklink_ids: list[str | int]) -> dict[str, tuple[str, str]]:
    """Return mapping alias → (design_id, name) for <=50 BrickLink ids.

    Works best under Rebrickable's rate‑limit; hard max is 100.
    Skips parts that are identified as sticker sheets (category ID 327)."""
    assert len(bricklink_ids) <= 50, "Pass at most 50 ids per call to avoid 429s"
    ids_param = ",".join(map(str, bricklink_ids))
    data = get_json(
        "/parts/",
        params={"bricklink_id__in": ids_param},
    )
    mapping: dict[str, tuple[str, str]] = {}
    for p in data.get("results", []):
        if p.get("part_category_id") == 327:
            continue  # Skip sticker sheets
        design_id = p["part_num"]
        name = p["name"]
        for bl in p["external_ids"].get("BrickLink", []):
            mapping[str(bl)] = (design_id, name)
    return mapping


def bulk_parts(design_ids: list[str]) -> dict[str, str]:
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
    except (RateLimitError, ExternalServiceError):
        mapping: dict[str, str] = {}
        for pid in design_ids:
            name = _single_part_name(pid)
            if name:
                mapping[pid] = name
        return mapping
    mapping: dict[str, str] = {}
    for part in data.get("results", []):
        mapping[part["part_num"]] = part["name"]
    return mapping

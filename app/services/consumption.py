"""Devin Consumption API client (aggregate ACU).

Per the Devin docs, ACU is NOT exposed on the session object — the only
programmatic source is the enterprise consumption API, which returns *aggregate
daily* ACU (not per-session):

    GET /v2/enterprise/consumption/daily   -> {total_acus, consumption_by_date, ...}

It requires an apk_user_* PAT with enterprise-admin permission AND the consumption
API enabled for the account (otherwise 403 "contact support to enable"). This
module degrades gracefully to None when unavailable, so total ACU shows honest-zero
until the account is entitled — then it populates with no further changes.

Docs: https://docs.devin.ai/api-reference/v2/consumption/daily-consumption
"""
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger()

_TTL_SECONDS = 300  # cache 5 min: the consumption API is an external, billing-scoped call
_cache: dict = {"ts": 0.0, "fetched": False, "value": None}


def _consumption_key() -> str:
    """Key used for the consumption API: prefer the dedicated Cognition/Devin
    enterprise key, fall back to the session key."""
    return settings.cog_api_key or settings.devin_api_key or ""


def is_configured() -> bool:
    key = _consumption_key()
    return bool(key) and "your" not in key.lower() and "placeholder" not in key.lower()


def get_total_acus(force: bool = False) -> Optional[float]:
    """Aggregate ACUs over the last ~30 days from the consumption API.
    Returns a float, or None if unavailable (not entitled / error). Cached 5 min,
    including the None result, so a gated account isn't polled on every request."""
    if not is_configured():
        return None
    now = time.time()
    if not force and _cache["fetched"] and (now - _cache["ts"]) < _TTL_SECONDS:
        return _cache["value"]

    # PST day boundary is 08:00 UTC; a wide window captures the current cycle.
    end = datetime.now(timezone.utc) + timedelta(days=1)
    start = end - timedelta(days=31)
    params = {"start_date": start.strftime("%Y-%m-%d"), "end_date": end.strftime("%Y-%m-%d")}
    headers = {"Authorization": f"Bearer {_consumption_key()}"}

    value: Optional[float] = None
    try:
        r = httpx.get(
            f"{settings.devin_api_url}/v2/enterprise/consumption/daily",
            headers=headers, params=params, timeout=8.0,
        )
        if r.status_code == 200:
            total = r.json().get("total_acus")
            value = float(total) if isinstance(total, (int, float)) else None
        else:
            logger.info("Consumption API unavailable", status=r.status_code)
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("Consumption API call failed", error=str(e))

    _cache.update(ts=now, fetched=True, value=value)
    return value


def get_status() -> dict:
    """Surface consumption-API availability for the dashboard/debugging."""
    cap = settings.max_acu_limit  # real per-session cost guardrail; always known
    if not is_configured():
        return {"enabled": False, "reason": "DEVIN_API_KEY not configured", "total_acus": None, "cap_per_session": cap}
    val = get_total_acus()
    if val is None:
        return {
            "enabled": False,
            "reason": "Consumption API not entitled — keys are wired but Devin returns 403; ask Devin to enable the consumption API for this account",
            "total_acus": None,
            "cap_per_session": cap,
        }
    return {"enabled": True, "reason": None, "total_acus": val, "cap_per_session": cap}

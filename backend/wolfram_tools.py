"""Wolfram Alpha LLM API client.

Targets the LLM API (https://www.wolframalpha.com/api/v1/llm-api), not the
classic Full Results API. The LLM API returns plaintext already shaped for
language-model consumption (input interpretation, result, alternate forms,
series, plot image URLs) — no pod/subpod XML parsing required.
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

LLM_API_URL = "https://www.wolframalpha.com/api/v1/llm-api"

# Heavy symbolic queries can be slow; allow tuning without a code change.
REQUEST_TIMEOUT = float(os.getenv("WOLFRAM_TIMEOUT", "30"))

# Wolfram clamps maxchars itself, but keep a sane local ceiling so a single
# query can't blow the agent's context window.
MAXCHARS_FLOOR = 200
MAXCHARS_CEILING = 25000


async def query_wolfram(
    app_id: str,
    query: str,
    maxchars: int = 6800,
    units: str = "metric",
) -> str:
    """Call the Wolfram Alpha LLM API and return its plaintext response.

    Args:
        app_id: Wolfram Alpha AppID.
        query: Natural-language or math query.
        maxchars: Approx. response length budget (clamped 200..25000).
        units: "metric" or "imperial".

    Returns:
        Plaintext response on success. On a non-success status, a single
        line prefixed with "Error:" describing what Wolfram reported
        (the LLM API puts useful suggestions in the body of a 501).
    """
    query = (query or "").strip()
    if not query:
        return "Error: empty query"

    try:
        maxchars = int(maxchars)
    except (TypeError, ValueError):
        maxchars = 6800
    maxchars = max(MAXCHARS_FLOOR, min(maxchars, MAXCHARS_CEILING))
    units = units if units in ("metric", "imperial") else "metric"

    params = {
        "input": query,
        "appid": app_id,
        "maxchars": maxchars,
        "units": units,
    }

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            r = await client.get(LLM_API_URL, params=params)
    except httpx.TimeoutException:
        return f"Error: Wolfram Alpha request timed out after {REQUEST_TIMEOUT:g}s"
    except httpx.HTTPError as e:
        return f"Error: HTTP request to Wolfram Alpha failed: {e}"

    body = (r.text or "").strip()

    if r.status_code == 200:
        return body or "Error: Wolfram Alpha returned an empty response"

    if r.status_code == 403:
        # Body is usually "Invalid appid" or "Appid missing".
        logger.warning("Wolfram Alpha 403: %s", body[:200])
        return f"Error: Wolfram Alpha rejected the AppID (403): {body or 'invalid appid'}"

    if r.status_code == 400:
        return f"Error: Wolfram Alpha could not parse the request (400): {body or 'bad request'}"

    if r.status_code == 501:
        # "Wolfram|Alpha did not understand your input" — body often carries
        # disambiguation suggestions worth showing the agent verbatim.
        return (
            "Error: Wolfram Alpha did not understand the input (501). "
            f"{body or 'Try rephrasing the query.'}"
        )

    logger.warning("Wolfram Alpha unexpected status %s: %s", r.status_code, body[:200])
    return f"Error: Wolfram Alpha returned HTTP {r.status_code}: {body[:500]}"

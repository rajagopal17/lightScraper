"""Best-effort OpenAI enrichment for notices that already passed the free
keyword classifier in classify.py.

Every guardrail here exists to bound token/dollar burn and keep this step
from ever being load-bearing: if OpenAI is slow, down, misconfigured, out of
budget, or returns garbage, `get_ai_context` returns None and the caller
stores the notice exactly as it would without AI at all. The keyword
classifier -- not this module -- is what decides inclusion/exclusion; this
module only adds a relevance label + short rationale on top.
"""

import json
import logging
from dataclasses import dataclass
from typing import Optional

from . import config
from .retry import with_retry

logger = logging.getLogger(__name__)

_client = None
_calls_made = 0

_SYSTEM_PROMPT = (
    "You assess ADB consulting notices for NGO (not-for-profit organization) "
    "suitability. Given a notice title and expertise text, reply with ONLY "
    'compact JSON, no prose, no markdown fences: {"relevance": "high|medium|low", '
    '"summary": "<=25 words on why an NGO would or would not take this on"}.'
)


@dataclass
class AIContext:
    relevance: str
    summary: str
    model: str


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI  # imported lazily: optional dependency path

        _client = OpenAI(api_key=config.OPENAI_API_KEY, timeout=config.AI_TIMEOUT_SECONDS)
    return _client


def _call_openai(title: str, expertise: str) -> dict:
    client = _get_client()
    text = f"Title: {title}\nExpertise: {expertise}"[: config.AI_MAX_INPUT_CHARS]
    response = client.chat.completions.create(
        model=config.OPENAI_MODEL,
        max_tokens=config.AI_MAX_OUTPUT_TOKENS,
        temperature=0,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        timeout=config.AI_TIMEOUT_SECONDS,
    )
    content = response.choices[0].message.content or ""
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`").removeprefix("json").strip()
    return json.loads(content)


_call_openai_with_retry = with_retry(
    _call_openai,
    max_attempts=config.AI_MAX_RETRY_ATTEMPTS,
    base_delay=config.AI_RETRY_BASE_DELAY_SECONDS,
)


def reset_call_budget() -> None:
    """Resets the per-run AI call counter. Called once at the start of
    scrape_once so the AI_MAX_CALLS_PER_RUN cap applies per run, not
    cumulatively across the process lifetime."""
    global _calls_made
    _calls_made = 0


def get_ai_context(title: str, expertise: str) -> Optional[AIContext]:
    """Returns an AIContext, or None if AI enrichment is disabled,
    unconfigured, over budget, or failed after retries. Never raises."""
    global _calls_made

    if not config.ENABLE_AI_CONTEXT:
        return None
    if not config.OPENAI_API_KEY:
        logger.debug("AI context disabled: OPENAI_API_KEY not set")
        return None
    if _calls_made >= config.AI_MAX_CALLS_PER_RUN:
        logger.warning(
            "AI call budget (%d) exhausted this run; skipping AI context for remaining notices",
            config.AI_MAX_CALLS_PER_RUN,
        )
        return None

    _calls_made += 1
    try:
        data = _call_openai_with_retry(title, expertise)
        relevance = str(data.get("relevance", "")).strip().lower() or "unknown"
        summary = str(data.get("summary", "")).strip()[:500]
        return AIContext(relevance=relevance, summary=summary, model=config.OPENAI_MODEL)
    except Exception as exc:  # noqa: BLE001 - AI enrichment is always best-effort
        logger.warning(
            "AI context call failed after %d attempt(s), falling back to keyword-only: %s",
            config.AI_MAX_RETRY_ATTEMPTS,
            exc,
        )
        return None

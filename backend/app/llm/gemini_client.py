import asyncio
from functools import lru_cache
import logging
import time
from typing import Any, Optional
from google import genai
from app.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_genai_client():
    """Return a google.genai Client configured for Vertex AI or API-key auth."""
    if settings.GOOGLE_GENAI_USE_ENTERPRISE:
        # Cloud Run handles auth automatically via ADC
        return genai.Client(
            vertexai=True,
            project=settings.GOOGLE_CLOUD_PROJECT,
            location=settings.GOOGLE_CLOUD_LOCATION,
        )
    else:
        # Legacy API key fallback
        return genai.Client(api_key=settings.GOOGLE_API_KEY)



class GeminiUnavailableError(Exception):
    """Raised when Gemini API remains unavailable after all retry attempts."""


_llm_dead_until: float = 0.0
_LLM_DAILY_COOLDOWN = 300  # 5 minutes
_LLM_TRANSIENT_COOLDOWN = 30  # 30 seconds
_LLM_DEAD_COOLDOWN = _LLM_TRANSIENT_COOLDOWN


def reset_cooldown() -> None:
    """Reset LLM cooldown timestamp (primarily for tests)."""
    global _llm_dead_until
    _llm_dead_until = 0.0


FALLBACK_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.8-flash",
]


def _is_retryable_error(exc: Exception) -> bool:
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return True
    err_str = str(exc).lower()
    # 429 daily quota is NOT retryable within a request — it resets in hours
    if "resource_exhausted" in err_str or "429" in err_str:
        if "per_day" in err_str or "generate_content_free_tier_requests" in err_str:
            return False  # daily quota — do not retry
    non_retryable_codes = ["400", "401", "403", "invalid_argument", "permission_denied", "unauthenticated"]
    if any(code in err_str for code in non_retryable_codes):
        return False
    retryable_codes = ["429", "503", "504", "resourceexhausted", "unavailable", "deadline", "timeout"]
    return any(code in err_str for code in retryable_codes)


def _sync_generate_content(api_client, model, contents, **kwargs):
    return api_client.models.generate_content(
        model=model,
        contents=contents,
        **kwargs,
    )


async def call_gemini_with_retry(
    contents: Any = None,
    prompt: Any = None,
    model: Optional[str] = None,
    max_attempts: int = 3,
    timeout: int = 30,
    user_id: Optional[Any] = None,
    config: Optional[Any] = None,
    client: Optional[Any] = None,
    backoff_delays: Optional[list[float]] = None,
    fallback_models: Optional[list[str]] = None,
    **kwargs,
) -> Any:
    """
    Execute a Gemini generate_content call with exponential backoff on 429/503/504 errors.
    Automatically tries fallback models if the primary model fails after max_attempts.
    Asynchronously sleeps during backoff to avoid blocking the event loop.
    Default backoff sequence: 1s -> 4s -> 16s.
    Logs structured telemetry and token counts.
    Raises GeminiUnavailableError on final failure across all models.
    """
    global _llm_dead_until
    if time.monotonic() < _llm_dead_until:
        raise GeminiUnavailableError("LLM in cooldown after recent failures")

    if contents is None:
        contents = prompt
    if contents is None:
        raise ValueError("Either contents or prompt must be provided to call_gemini_with_retry.")

    primary = model or settings.GEMINI_MODEL
    if settings.GOOGLE_GENAI_USE_ENTERPRISE and primary.startswith("models/"):
        primary = primary.removeprefix("models/")
    api_client = client or get_genai_client()

    if fallback_models is not None:
        models_to_try = [
            (m.removeprefix("models/") if settings.GOOGLE_GENAI_USE_ENTERPRISE and m.startswith("models/") else m)
            for m in fallback_models
        ]
    else:
        resolved_fallbacks = settings.resolved_fallback_models
        models_to_try = [primary] + [m for m in resolved_fallbacks if m != primary]

    delays = backoff_delays if backoff_delays is not None else [1.0, 4.0, 16.0]
    tried_models = []
    last_exception = None

    for current_model in models_to_try:
        tried_models.append(current_model)
        for attempt in range(1, max_attempts + 1):
            try:
                call_kwargs = {}
                if config is not None:
                    call_kwargs["config"] = config
                call_kwargs.update(kwargs)

                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        _sync_generate_content,
                        api_client,
                        current_model,
                        contents,
                        **call_kwargs,
                    ),
                    timeout=float(timeout),
                )

                input_tokens = getattr(getattr(response, "usage_metadata", None), "prompt_token_count", None)
                output_tokens = getattr(getattr(response, "usage_metadata", None), "candidates_token_count", None)
                logger.info(
                    "Gemini call succeeded: model=%s user_id=%s attempt=%d input_tokens=%s output_tokens=%s",
                    current_model,
                    user_id or "anonymous",
                    attempt,
                    input_tokens,
                    output_tokens,
                )
                return response

            except Exception as exc:
                last_exception = exc
                is_retryable = _is_retryable_error(exc)
                if not is_retryable:
                    logger.warning(
                        "Non-retryable error on model %s: %s. Raising immediately.",
                        current_model,
                        exc,
                    )
                    err_str = str(exc).lower()
                    if ("resource_exhausted" in err_str or "429" in err_str) and (
                        "per_day" in err_str or "generate_content_free_tier_requests" in err_str
                    ):
                        _llm_dead_until = time.monotonic() + _LLM_DAILY_COOLDOWN
                    else:
                        _llm_dead_until = time.monotonic() + _LLM_TRANSIENT_COOLDOWN
                    raise exc

                logger.warning(
                    "Gemini call failed on attempt %d/%d for model %s: %s (retryable=%s)",
                    attempt,
                    max_attempts,
                    current_model,
                    exc,
                    is_retryable,
                )
                if attempt < max_attempts:
                    delay = delays[attempt - 1] if (attempt - 1) < len(delays) else delays[-1]
                    await asyncio.sleep(delay)
                else:
                    logger.warning(
                        "Model %s unavailable after %d attempts, trying next",
                        current_model,
                        max_attempts,
                    )
                    break

    _llm_dead_until = time.monotonic() + _LLM_TRANSIENT_COOLDOWN
    raise GeminiUnavailableError(
        f"All models failed: {tried_models}. Last error: {last_exception}"
    ) from last_exception

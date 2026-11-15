import asyncio
from functools import lru_cache
import logging
import time
from typing import Any, Optional, List
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


_UNAVAILABLE_MODEL_IDS: set[str] = set()


def mark_model_unavailable(model: str) -> None:
    """Permanently mark a model ID as unavailable for the process lifetime (e.g. on 404/NOT_FOUND)."""
    if not model:
        return
    clean = model.removeprefix("models/")
    _UNAVAILABLE_MODEL_IDS.add(model)
    _UNAVAILABLE_MODEL_IDS.add(clean)


def is_model_unavailable(model: str) -> bool:
    """Check if model ID is marked unavailable."""
    if not model:
        return False
    clean = model.removeprefix("models/")
    return clean in _UNAVAILABLE_MODEL_IDS or model in _UNAVAILABLE_MODEL_IDS


def reset_cooldown() -> None:
    """Reset LLM cooldown timestamp and unavailable models (primarily for tests)."""
    global _llm_dead_until
    _llm_dead_until = 0.0
    _UNAVAILABLE_MODEL_IDS.clear()


def clear_unavailable_models() -> None:
    """Clear sticky unavailable models cache (primarily for tests)."""
    _UNAVAILABLE_MODEL_IDS.clear()


FALLBACK_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
]

MODEL_FALLBACK_CHAIN = [
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
]


def get_fallback_models(primary_model: Optional[str] = None) -> list[str]:
    """
    Returns an ordered chain of fallback models for streaming/query:
    1. Primary configured model (settings.PRIMARY_CHAT_MODEL or settings.GEMINI_MODEL)
    2. Configured fallback models from settings.resolved_fallback_models (or MODEL_FALLBACK_CHAIN)
    Filters out models marked permanently unavailable for this process (e.g. via 404).
    """
    primary = primary_model or getattr(settings, "PRIMARY_CHAT_MODEL", None) or settings.GEMINI_MODEL
    if settings.GOOGLE_GENAI_USE_ENTERPRISE and primary.startswith("models/"):
        primary = primary.removeprefix("models/")

    chain = [primary]
    fallback_candidates = settings.resolved_fallback_models if settings.resolved_fallback_models else MODEL_FALLBACK_CHAIN
    for m in fallback_candidates:
        target = m.removeprefix("models/") if settings.GOOGLE_GENAI_USE_ENTERPRISE and m.startswith("models/") else m
        if target not in chain:
            chain.append(target)
    active_chain = [m for m in chain if not is_model_unavailable(m)]
    return active_chain if active_chain else chain


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


def _has_thinking_config(cfg: Any) -> bool:
    """Check if config has a thinking_config attached."""
    if cfg is None:
        return False
    if isinstance(cfg, dict):
        return "thinking_config" in cfg and cfg["thinking_config"] is not None
    return hasattr(cfg, "thinking_config") and getattr(cfg, "thinking_config", None) is not None


def _strip_thinking_config(cfg: Any) -> Any:
    """Return a copy of config with thinking_config removed or set to None."""
    if cfg is None:
        return None
    if isinstance(cfg, dict):
        new_cfg = dict(cfg)
        new_cfg.pop("thinking_config", None)
        return new_cfg
    try:
        import copy
        new_cfg = copy.copy(cfg)
        if hasattr(new_cfg, "thinking_config"):
            setattr(new_cfg, "thinking_config", None)
        return new_cfg
    except Exception:
        return None


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

    active_models_to_try = [m for m in models_to_try if not is_model_unavailable(m)]
    if not active_models_to_try:
        active_models_to_try = models_to_try

    for current_model in active_models_to_try:
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
                err_str = str(exc).lower()

                # Handle 400 / INVALID_ARGUMENT with thinking_config: retry immediately without thinking_config
                is_400 = "400" in err_str or "invalid_argument" in err_str or "invalid argument" in err_str
                if is_400 and _has_thinking_config(call_kwargs.get("config")):
                    logger.info(
                        "Model %s rejected thinking_config with 400; retrying immediately without thinking_config",
                        current_model,
                    )
                    retry_kwargs = dict(call_kwargs)
                    retry_kwargs["config"] = _strip_thinking_config(call_kwargs.get("config"))
                    try:
                        response = await asyncio.wait_for(
                            asyncio.to_thread(
                                _sync_generate_content,
                                api_client,
                                current_model,
                                contents,
                                **retry_kwargs,
                            ),
                            timeout=float(timeout),
                        )
                        input_tokens = getattr(getattr(response, "usage_metadata", None), "prompt_token_count", None)
                        output_tokens = getattr(getattr(response, "usage_metadata", None), "candidates_token_count", None)
                        logger.info(
                            "Gemini call succeeded without thinking_config: model=%s user_id=%s attempt=%d input_tokens=%s output_tokens=%s",
                            current_model,
                            user_id or "anonymous",
                            attempt,
                            input_tokens,
                            output_tokens,
                        )
                        return response
                    except Exception as retry_exc:
                        exc = retry_exc
                        last_exception = retry_exc
                        err_str = str(retry_exc).lower()

                # Handle 404 / NOT_FOUND: Model not enabled or doesn't exist on project/region
                if "404" in err_str or "not_found" in err_str or "not found" in err_str:
                    logger.warning(
                        "Model %s returned 404 NOT_FOUND. Marking as unavailable for process lifetime and trying next model.",
                        current_model,
                    )
                    mark_model_unavailable(current_model)
                    break

                is_retryable = _is_retryable_error(exc)
                if not is_retryable:
                    logger.warning(
                        "Non-retryable error on model %s: %s. Trying next fallback model.",
                        current_model,
                        exc,
                    )
                    if ("resource_exhausted" in err_str or "429" in err_str) and (
                        "per_day" in err_str or "generate_content_free_tier_requests" in err_str
                    ):
                        _llm_dead_until = time.monotonic() + _LLM_DAILY_COOLDOWN
                        raise exc
                    # Advance to next model in fallback chain
                    break

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

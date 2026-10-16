import asyncio
import logging
from typing import Any, Optional
from google import genai
from app.core.config import settings

logger = logging.getLogger(__name__)


class GeminiUnavailableError(Exception):
    """Raised when Gemini API remains unavailable after all retry attempts."""


FALLBACK_MODELS = [
    "gemini-3.8-flash",   # primary
    "gemini-3.6-flash",   # fallback 1
    "gemini-3.5-flash",   # fallback 2
    "gemini-2.5-flash",   # fallback 3 (older but always available)
]


def _is_retryable_error(exc: Exception) -> bool:
    err_str = str(exc).lower()
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
    if contents is None:
        contents = prompt
    if contents is None:
        raise ValueError("Either contents or prompt must be provided to call_gemini_with_retry.")

    primary = model or settings.GEMINI_MODEL
    api_client = client or genai.Client(api_key=settings.GOOGLE_API_KEY)

    if fallback_models is not None:
        models_to_try = fallback_models
    else:
        models_to_try = [primary] + [m for m in FALLBACK_MODELS if m != primary]

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

                response = await asyncio.to_thread(
                    _sync_generate_content,
                    api_client,
                    current_model,
                    contents,
                    **call_kwargs,
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

    raise GeminiUnavailableError(
        f"All models failed: {tried_models}. Last error: {last_exception}"
    ) from last_exception

import asyncio
import logging
from typing import Any, Optional
from google import genai
from app.core.config import settings
from app.llm.gemini_client import GeminiUnavailableError, _is_retryable_error, get_genai_client

logger = logging.getLogger(__name__)


def _sync_embed_content(api_client, model, contents, **kwargs):
    return api_client.models.embed_content(
        model=model,
        contents=contents,
        **kwargs,
    )


async def embed_content_with_retry(
    contents: Any,
    model: Optional[str] = None,
    max_attempts: int = 3,
    timeout: int = 30,
    user_id: Optional[Any] = None,
    config: Optional[Any] = None,
    client: Optional[Any] = None,
    backoff_delays: Optional[list[float]] = None,
    **kwargs,
) -> Any:
    """
    Execute a Gemini embed_content call with exponential backoff on 429/503/504 errors.
    Asynchronously sleeps during backoff to avoid blocking the event loop.
    Default backoff sequence: 1s -> 4s -> 16s.
    Logs structured telemetry.
    Raises GeminiUnavailableError on final failure.
    """
    target_model = model or "models/gemini-embedding-2"
    api_client = client or get_genai_client()

    last_exception = None
    delays = backoff_delays if backoff_delays is not None else [1.0, 4.0, 16.0]

    for attempt in range(1, max_attempts + 1):
        try:
            call_kwargs = {}
            if config is not None:
                call_kwargs["config"] = config
            call_kwargs.update(kwargs)

            response = await asyncio.to_thread(
                _sync_embed_content,
                api_client,
                target_model,
                contents,
                **call_kwargs,
            )
            logger.info(
                "Gemini embed call succeeded: model=%s user_id=%s attempt=%d",
                target_model,
                user_id or "anonymous",
                attempt,
            )
            return response

        except Exception as exc:
            last_exception = exc
            is_retryable = _is_retryable_error(exc)
            if not is_retryable:
                logger.warning(
                    "Non-retryable error on embedding model %s: %s. Raising immediately.",
                    target_model,
                    exc,
                )
                raise exc

            logger.warning(
                "Gemini embed call failed on attempt %d/%d for model %s: %s (retryable=%s)",
                attempt,
                max_attempts,
                target_model,
                exc,
                is_retryable,
            )
            if attempt < max_attempts:
                delay = delays[attempt - 1] if (attempt - 1) < len(delays) else delays[-1]
                await asyncio.sleep(delay)
            else:
                break

    raise GeminiUnavailableError(
        f"Gemini Embeddings API unavailable after {max_attempts} attempts "
        f"for model '{target_model}': {last_exception}"
    ) from last_exception

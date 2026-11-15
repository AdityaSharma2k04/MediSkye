import asyncio
import logging
from typing import Any, Optional, List
from app.core.config import settings
from app.llm.gemini_client import GeminiUnavailableError, _is_retryable_error, get_genai_client

logger = logging.getLogger(__name__)

_WORKING_EMBEDDING_MODEL: Optional[str] = None
_UNAVAILABLE_EMBEDDING_MODELS: set[str] = set()


def get_embedding_models_to_try(primary_model: Optional[str] = None) -> List[str]:
    """Return prioritized list of embedding models to try, filtering out permanently unavailable ones."""
    primary = primary_model or _WORKING_EMBEDDING_MODEL or settings.resolved_embedding_model
    if settings.GOOGLE_GENAI_USE_ENTERPRISE and primary.startswith("models/"):
        primary = primary.removeprefix("models/")

    chain = [primary]
    fallbacks = getattr(settings, "resolved_embedding_fallbacks", ["gemini-embedding-2", "gemini-embedding-001", "text-embedding-004"])
    for m in fallbacks:
        target = m.removeprefix("models/") if settings.GOOGLE_GENAI_USE_ENTERPRISE and m.startswith("models/") else m
        if target not in chain:
            chain.append(target)
    active = [m for m in chain if m not in _UNAVAILABLE_EMBEDDING_MODELS]
    return active if active else chain


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
    Automatically falls back across EMBEDDING_FALLBACK_CHAIN if a model is unavailable or 404s.
    Ensures 768-dimensional consistency.
    """
    global _WORKING_EMBEDDING_MODEL
    api_client = client or get_genai_client()
    models_to_try = get_embedding_models_to_try(model)
    delays = backoff_delays if backoff_delays is not None else [1.0, 4.0, 16.0]
    last_exception = None

    for target_model in models_to_try:
        for attempt in range(1, max_attempts + 1):
            try:
                call_kwargs = {}
                if config is not None:
                    call_kwargs["config"] = config
                else:
                    try:
                        from google.genai.types import EmbedContentConfig, HttpOptions
                        opt = HttpOptions(timeout=int(timeout * 1000)) if timeout and timeout > 0 else None
                        call_kwargs["config"] = EmbedContentConfig(
                            output_dimensionality=768,
                            http_options=opt,
                        )
                    except Exception:
                        pass
                call_kwargs.update(kwargs)

                coro = asyncio.to_thread(
                    _sync_embed_content,
                    api_client,
                    target_model,
                    contents,
                    **call_kwargs,
                )
                response = await asyncio.wait_for(coro, timeout=float(timeout))
                _WORKING_EMBEDDING_MODEL = target_model
                logger.info(
                    "Gemini embed call succeeded: model=%s user_id=%s attempt=%d",
                    target_model,
                    user_id or "anonymous",
                    attempt,
                )
                return response

            except Exception as exc:
                last_exception = exc
                err_str = str(exc).lower()

                # Handle 400 with output_dimensionality: retry without output_dimensionality if rejected
                is_400 = "400" in err_str or "invalid_argument" in err_str or "invalid argument" in err_str
                if is_400 and ("output_dimensionality" in err_str or "dimensionality" in err_str or "dimension" in err_str):
                    logger.info("Embedding model %s rejected output_dimensionality; retrying without it", target_model)
                    try:
                        from google.genai.types import EmbedContentConfig, HttpOptions
                        opt = HttpOptions(timeout=int(timeout * 1000)) if timeout and timeout > 0 else None
                        retry_kwargs = dict(call_kwargs)
                        retry_kwargs["config"] = EmbedContentConfig(http_options=opt)
                        response = await asyncio.wait_for(
                            asyncio.to_thread(
                                _sync_embed_content,
                                api_client,
                                target_model,
                                contents,
                                **retry_kwargs,
                            ),
                            timeout=float(timeout),
                        )
                        _WORKING_EMBEDDING_MODEL = target_model
                        return response
                    except Exception as retry_exc:
                        exc = retry_exc
                        last_exception = retry_exc
                        err_str = str(retry_exc).lower()

                # Handle 404 / NOT_FOUND: Mark model unavailable and try next model immediately
                if "404" in err_str or "not_found" in err_str or "not found" in err_str:
                    logger.warning(
                        "Embedding model %s returned 404 NOT_FOUND. Marking as unavailable and trying next model in chain.",
                        target_model,
                    )
                    _UNAVAILABLE_EMBEDDING_MODELS.add(target_model)
                    break

                is_retryable = isinstance(exc, (TimeoutError, asyncio.TimeoutError)) or _is_retryable_error(exc)
                if not is_retryable:
                    logger.warning(
                        "Non-retryable error on embedding model %s: %s. Trying next fallback model.",
                        target_model,
                        exc,
                    )
                    break

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
        f"Gemini Embeddings API unavailable after {max_attempts} attempts across models {models_to_try}: {last_exception}"
    ) from last_exception

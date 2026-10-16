"""Agent Router LLM client — OpenAI-compatible provider."""
import httpx
import json
import asyncio
import logging
from typing import AsyncIterator, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

FALLBACK_MODELS = [
    "claude-opus-5-5",       # 1. Best Claude
    "claude-opus-5",         # 2. Claude Opus 5
    "claude-opus-4-8",       # 3. Claude Opus 4.8
    "gpt-6-astra",           # 4. Best GPT
    "gpt-5.6-sol",           # 5. GPT-5.6 Sol
    "deepseek-v4-flash",     # 6. DeepSeek V4 Flash
    "glm-5.3",               # 7. GLM 5.3
]


class AgentRouterError(Exception):
    """Raised when Agent Router is unavailable after all fallbacks."""


async def _stream_one_model(
    model: str,
    system_instruction: str,
    user_content: str,
    timeout: float = 15.0,
) -> AsyncIterator[str]:
    """Stream from a single Agent Router model. Yields text chunks."""
    url = f"{settings.AGENTROUTER_BASE_URL}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_content},
        ],
        "stream": True,
    }
    headers = {
        "Authorization": f"Bearer {settings.AGENTROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", url, json=payload, headers=headers) as response:
            if response.status_code != 200:
                body = await response.aread()
                raise AgentRouterError(
                    f"{model}: HTTP {response.status_code} — {body[:200]!r}"
                )

            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:].strip()
                if data == "[DONE]":
                    return
                try:
                    chunk = json.loads(data)
                    text = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
                    if text:
                        yield text
                except json.JSONDecodeError:
                    continue


async def call_agentrouter_stream(
    system_instruction: str,
    user_content: str,
    model: Optional[str] = None,
) -> AsyncIterator[str]:
    """
    Stream from Agent Router with automatic model fallback:
    Claude → GPT → DeepSeek.

    Tries each model in order. If a model fails BEFORE yielding any content, 
    moves to the next. Once a model yields content, no fallback (avoids 
    duplicated output).
    """
    if not settings.AGENTROUTER_API_KEY:
        raise AgentRouterError("AGENTROUTER_API_KEY not configured")

    models_to_try = [model] if model else FALLBACK_MODELS
    last_error = None

    for current_model in models_to_try:
        yielded_any = False
        try:
            async for text in _stream_one_model(current_model, system_instruction, user_content):
                yielded_any = True
                yield text
            return  # success
        except Exception as e:
            last_error = e
            if yielded_any:
                # Partial content already streamed — don't fall back
                raise AgentRouterError(
                    f"Stream failed mid-response on {current_model}: {e}"
                ) from e
            logger.warning("Agent Router model %s failed: %s. Trying next.", current_model, e)
            continue

    raise AgentRouterError(
        f"All Agent Router models failed. Please select Gemini model from the drop down menu. Last error: {last_error}"
    )


async def call_agentrouter(
    system_instruction: str,
    user_content: str,
    model: Optional[str] = None,
) -> str:
    """Non-streaming — collect full response."""
    chunks = []
    async for chunk in call_agentrouter_stream(system_instruction, user_content, model):
        chunks.append(chunk)
    return "".join(chunks)

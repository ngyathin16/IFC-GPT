"""LLM client factory for the IFC generation agent.

Provides a single ``get_llm()`` function that returns a LangChain-compatible
chat model backed by the Azure OpenAI **Responses API** endpoint.

``gpt-5.1-codex-max`` only supports ``POST /openai/responses`` — NOT the
Chat Completions endpoint used by ``AzureChatOpenAI``.  This module wraps
that API in a minimal ``BaseChatModel`` subclass so the rest of the agent
can call ``.invoke()`` / ``.stream()`` as normal.

Environment variables (set in .env):
    AZURE_OPENAI_API_KEY       — Azure resource key
    AZURE_OPENAI_ENDPOINT      — Full endpoint URL, e.g.
                                 https://ov-virginia.cognitiveservices.azure.com/openai/responses?api-version=2025-04-01-preview
    AZURE_OPENAI_DEPLOYMENT    — Model name / deployment (e.g. gpt-5.1-codex-max)
    AZURE_OPENAI_API_VERSION   — API version string (e.g. 2025-04-01-preview)
    OPENAI_API_KEY             — Fallback plain OpenAI key
    OPENAI_BASE_URL            — Fallback base URL
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Iterator, List, Optional, Sequence

from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singleton so every node reuses the same client object
# ---------------------------------------------------------------------------

_llm_instance = None


# ---------------------------------------------------------------------------
# Custom wrapper for the Azure OpenAI Responses API
# ---------------------------------------------------------------------------


class AzureResponsesChatModel(BaseChatModel):
    """Minimal LangChain BaseChatModel backed by the Azure OpenAI Responses API.

    The Responses API schema differs from Chat Completions:
      - Input:  {"model": ..., "input": [{"role": ..., "content": ...}]}
      - Output: {"output": [{"type": "message", "content": [{"text": ...}]}]}
    """

    api_key: str
    endpoint: str          # full URL including api-version query string
    model: str
    temperature: float = 0.2

    @property
    def _llm_type(self) -> str:
        return "azure-responses-api"

    def _convert_messages(self, messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        """Convert LangChain messages to Responses API input format."""
        converted: List[Dict[str, Any]] = []
        for m in messages:
            if isinstance(m, SystemMessage):
                converted.append({"role": "system", "content": str(m.content)})
            elif isinstance(m, HumanMessage):
                converted.append({"role": "user", "content": str(m.content)})
            elif isinstance(m, AIMessage):
                converted.append({"role": "assistant", "content": str(m.content)})
            else:
                converted.append({"role": "user", "content": str(m.content)})
        return converted

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> ChatResult:
        import requests  # type: ignore[import]

        payload: Dict[str, Any] = {
            "model": self.model,
            "input": self._convert_messages(messages),
        }
        if stop:
            payload["stop"] = stop

        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json",
        }

        logger.info(f"[llm] Responses API → {self.endpoint[:60]}...")
        resp = requests.post(self.endpoint, json=payload, headers=headers, timeout=120)

        if not resp.ok:
            raise ValueError(
                f"Azure Responses API error {resp.status_code}: {resp.text[:400]}"
            )

        data = resp.json()
        text = ""
        for item in data.get("output", []):
            if item.get("type") == "message":
                for part in item.get("content", []):
                    if isinstance(part, dict):
                        text += part.get("text", "")
                    elif isinstance(part, str):
                        text += part

        message = AIMessage(content=text)
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------


def get_llm(temperature: float = 0.2) -> BaseChatModel:
    """Return a cached LangChain chat-model instance.

    Uses the Azure Responses API when ``AZURE_OPENAI_API_KEY`` is set,
    otherwise falls back to ``langchain_openai.ChatOpenAI``.

    Args:
        temperature: Sampling temperature (lower = more deterministic).

    Returns:
        A ``BaseChatModel`` instance ready for ``.invoke()``.
    """
    global _llm_instance
    if _llm_instance is not None:
        return _llm_instance  # type: ignore[return-value]

    azure_key = os.getenv("AZURE_OPENAI_API_KEY", "")
    azure_endpoint = os.getenv(
        "AZURE_OPENAI_ENDPOINT",
        "https://ov-virginia.cognitiveservices.azure.com/openai/responses?api-version=2025-04-01-preview",
    )
    azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.1-codex-max")

    if azure_key:
        logger.info(
            f"[llm] Using Azure Responses API: model={azure_deployment}"
        )
        _llm_instance = AzureResponsesChatModel(
            api_key=azure_key,
            endpoint=azure_endpoint,
            model=azure_deployment,
            temperature=temperature,
        )
        return _llm_instance  # type: ignore[return-value]

    # Fallback: plain OpenAI-compatible
    openai_key = os.getenv("OPENAI_API_KEY", "")
    openai_base = os.getenv("OPENAI_BASE_URL", "")

    logger.info("[llm] Falling back to plain OpenAI endpoint")

    from langchain_openai import ChatOpenAI  # type: ignore[import]

    kwargs: dict = {"temperature": temperature, "model": "gpt-5.1-codex-max"}
    if openai_key:
        kwargs["api_key"] = openai_key  # type: ignore[assignment]
    if openai_base:
        kwargs["base_url"] = openai_base

    _llm_instance = ChatOpenAI(**kwargs)
    return _llm_instance  # type: ignore[return-value]

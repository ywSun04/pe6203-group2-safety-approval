"""Environment checks for a pinned AgentDojo model.

The check runs before a client is constructed, so a missing key does not start a request.
"""

from __future__ import annotations

import os
import socket

from agentdojo.models import MODEL_PROVIDERS, ModelsEnum


def missing_model_settings(model: str, model_id: str | None = None) -> list[str]:
    """Return the settings this model still needs. An empty list means the client can be built."""
    try:
        provider = MODEL_PROVIDERS[ModelsEnum(model)]
    except ValueError as error:
        known = ", ".join(item.value for item in ModelsEnum)
        raise ValueError(f"Unknown model {model!r}. Use one of: {known}") from error

    missing: list[str] = []
    if provider == "openai":
        _need(missing, "OPENAI_API_KEY")
    elif provider == "anthropic":
        _need(missing, "ANTHROPIC_API_KEY")
    elif provider in {"together", "together-prompting"}:
        _need(missing, "TOGETHER_API_KEY")
    elif provider == "cohere":
        if not (os.getenv("CO_API_KEY") or os.getenv("COHERE_API_KEY")):
            missing.append("CO_API_KEY or COHERE_API_KEY")
    elif provider == "google":
        _need(missing, "GCP_PROJECT")
        _need(missing, "GCP_LOCATION")
    elif provider == "openai-compatible":
        _need(missing, "OPENAI_COMPATIBLE_BASE_URL")
        _need(missing, "OPENAI_COMPATIBLE_API_KEY")
        if not model_id:
            missing.append("--model-id")
    elif provider in {"local", "vllm_parsed"}:
        port_text = os.getenv("LOCAL_LLM_PORT", "8000")
        if not _tcp_open("127.0.0.1", port_text):
            missing.append(f"a model server at 127.0.0.1:{port_text} (LOCAL_LLM_PORT)")
    else:
        missing.append(f"a supported provider setting for {provider}")
    return missing


def _need(missing: list[str], name: str) -> None:
    if not os.getenv(name):
        missing.append(name)


def _tcp_open(host: str, port_text: str) -> bool:
    try:
        port = int(port_text)
    except ValueError:
        return False
    try:
        with socket.create_connection((host, port), timeout=0.3):
            return True
    except OSError:
        return False

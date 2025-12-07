"""LLM client utilities for Smart Vacation Planner."""

import json
import requests

# Central point to change model names for Ollama calls.
DEFAULT_OLLAMA_MODEL = "qwen3:4b-instruct"


class LLMError(Exception):
    """Custom exception for LLM-related failures."""


def _extract_assistant_content(data):
    """Extract assistant content from typical Ollama chat responses."""
    if isinstance(data, dict):
        message = data.get("message")
        if isinstance(message, dict) and message.get("content"):
            return message["content"]

        messages = data.get("messages")
        if isinstance(messages, list):
            for entry in reversed(messages):
                if (
                    isinstance(entry, dict)
                    and entry.get("role") == "assistant"
                    and entry.get("content")
                ):
                    return entry["content"]
    return None


def call_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    model: str = DEFAULT_OLLAMA_MODEL,
    base_url: str = "http://localhost:11434",
) -> str:
    """
    Call a local Ollama model via the /api/chat endpoint and return assistant text.

    Raises:
        LLMError: When the request fails or no assistant content is found.
    """
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "stream": False,  # avoid NDJSON streaming; request a single JSON response
    }
    try:
        # No timeout so local models can take as long as needed.
        response = requests.post(f"{base_url}/api/chat", json=payload, timeout=None)
    except requests.RequestException as exc:
        raise LLMError(f"Failed to reach Ollama at {base_url}: {exc}") from exc

    if response.status_code != 200:
        raise LLMError(
            f"Ollama returned HTTP {response.status_code}: {response.text.strip()}"
        )

    data = None
    try:
        data = response.json()
    except ValueError:
        # Fallback: handle streamed NDJSON concatenated in the body.
        text = response.text.replace("} {", "}\n{")
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        for line in reversed(lines):
            try:
                data = json.loads(line)
                break
            except json.JSONDecodeError:
                continue
        if data is None:
            raise LLMError(f"Invalid JSON from Ollama: {response.text}")

    content = _extract_assistant_content(data)
    if content:
        return content

    raise LLMError(f"No assistant content found in response: {data}")

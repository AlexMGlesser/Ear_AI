from typing import Any
import re
import httpx

from .config import settings


async def generate_reply(
    user_text: str,
    system_prompt: str,
    history_messages: list[dict[str, str]] | None = None,
) -> str:
    strict_system_prompt = (
        f"{system_prompt}\n\n"
        "Do not expose internal reasoning. Reply with only the final answer in plain text."
    )

    history = history_messages or []

    payload: dict[str, Any] = {
        "model": settings.lm_studio_model,
        "messages": [
            {"role": "system", "content": strict_system_prompt},
            *history,
            {"role": "user", "content": f"/no_think\n{user_text}"},
        ],
        "temperature": 0.2,
        "max_tokens": 120,
    }

    url = f"{settings.lm_studio_base_url.rstrip('/')}/v1/chat/completions"

    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

    choices = data.get("choices") or []
    if not choices:
        return "I could not generate a response right now."

    # LM Studio models can return content in several OpenAI-compatible shapes.
    for choice in choices:
        content = _extract_choice_text(choice)
        if content:
            return content

    return "I do not have a response right now."


def _extract_choice_text(choice: dict[str, Any]) -> str:
    message = choice.get("message") or {}

    content = message.get("content")
    if isinstance(content, str):
        text = _strip_reasoning_artifacts(content)
        if text:
            return text

    # Some compatible endpoints return content as a list of parts.
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                if item.strip():
                    parts.append(item.strip())
                continue

            if not isinstance(item, dict):
                continue

            text_value = item.get("text")
            if isinstance(text_value, str) and text_value.strip():
                parts.append(text_value.strip())

        merged = _strip_reasoning_artifacts(" ".join(parts))
        if merged:
            return merged

    # Some servers may still return the legacy completion text shape.
    legacy_text = choice.get("text")
    if isinstance(legacy_text, str):
        cleaned_legacy = _strip_reasoning_artifacts(legacy_text)
        if cleaned_legacy:
            return cleaned_legacy

    refusal = message.get("refusal")
    if isinstance(refusal, str) and refusal.strip():
        return refusal.strip()

    output_text = choice.get("output_text")
    if isinstance(output_text, str):
        cleaned_output = _strip_reasoning_artifacts(output_text)
        if cleaned_output:
            return cleaned_output

    return ""


def _strip_reasoning_artifacts(text: str) -> str:
    cleaned = text

    # Remove common thought tags some reasoning models include.
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)

    # Remove prefixed reasoning headers if they leak into plain text outputs.
    cleaned = re.sub(r"(?im)^\s*(reasoning|thoughts?)\s*:\s*.*$", "", cleaned)

    # Collapse excess blank lines after removals.
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()

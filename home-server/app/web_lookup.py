from __future__ import annotations

from urllib.parse import quote
import re
import httpx

from .config import settings


def should_lookup(user_text: str) -> bool:
    text = user_text.lower()

    meta_patterns = (
        "did you check the internet",
        "did you check internet",
        "did you look it up",
        "did you search",
        "did you really check",
    )
    if any(pattern in text for pattern in meta_patterns):
        return False

    small_talk = (
        "hello",
        "hi",
        "how are you",
        "thanks",
        "thank you",
        "good morning",
        "good night",
    )
    if any(text.strip() == phrase for phrase in small_talk):
        return False

    triggers = (
        "look up",
        "lookup",
        "search",
        "internet",
        "find",
        "today",
        "latest",
        "current",
        "news",
        "price",
        "stock",
        "weather",
        "who is",
        "what is",
        "when did",
        "where is",
        "update",
    )
    if any(token in text for token in triggers):
        return True

    question_starts = (
        "who",
        "what",
        "when",
        "where",
        "why",
        "how",
        "is",
        "are",
        "can",
        "should",
        "could",
    )
    normalized = text.strip()
    if normalized.endswith("?"):
        return True

    return normalized.startswith(question_starts)


async def build_web_context(user_text: str) -> str:
    if not settings.web_lookup_enabled:
        return ""

    query = user_text.strip()
    if not query:
        return ""

    snippets: list[str] = []

    async with httpx.AsyncClient(timeout=settings.web_lookup_timeout_seconds) as client:
        # DuckDuckGo HTML search result snippets (read-only lookup).
        ddg = await _fetch_duckduckgo_html(client, query, settings.web_lookup_max_results)
        if ddg:
            snippets.extend(ddg)

        # Wikipedia search + summaries for factual lookup.
        wiki = await _fetch_wikipedia(client, query, settings.web_lookup_max_results)
        if wiki:
            snippets.extend(wiki)

    if not snippets:
        return ""

    merged = "\n".join(f"- {item}" for item in snippets[: settings.web_lookup_max_results])
    return (
        "Web lookup notes (read-only references; may be incomplete):\n"
        f"{merged}"
    )


async def _fetch_duckduckgo(client: httpx.AsyncClient, query: str) -> list[str]:
    # Deprecated path kept for compatibility with previous imports.
    return await _fetch_duckduckgo_html(client, query, settings.web_lookup_max_results)


async def _fetch_duckduckgo_html(
    client: httpx.AsyncClient,
    query: str,
    max_results: int,
) -> list[str]:
    url = "https://html.duckduckgo.com/html/"
    headers = {
        "User-Agent": "EarAI-HomeServer/1.0",
    }

    try:
        response = await client.post(url, data={"q": query}, headers=headers)
        response.raise_for_status()
        html = response.text
    except Exception:
        return []

    snippets: list[str] = []
    # Extract title/snippet pairs from DDG HTML response.
    title_pattern = re.compile(r'<a[^>]*class="result__a"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
    snippet_pattern = re.compile(
        r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>|<div[^>]*class="result__snippet"[^>]*>(.*?)</div>',
        re.IGNORECASE | re.DOTALL,
    )

    titles = [_strip_tags(t) for t in title_pattern.findall(html)]
    raw_snippets = snippet_pattern.findall(html)
    parsed_snippets = [_strip_tags(a or b) for a, b in raw_snippets]

    for idx, title in enumerate(titles[:max_results]):
        snippet = parsed_snippets[idx] if idx < len(parsed_snippets) else ""
        if snippet:
            snippets.append(f"DuckDuckGo ({title}): {snippet}")
        elif title:
            snippets.append(f"DuckDuckGo: {title}")

    return snippets


async def _fetch_wikipedia(
    client: httpx.AsyncClient,
    query: str,
    max_results: int,
) -> list[str]:
    search_url = "https://en.wikipedia.org/w/rest.php/v1/search/title"

    try:
        response = await client.get(search_url, params={"q": query, "limit": max_results})
        response.raise_for_status()
        data = response.json()
    except Exception:
        return []

    pages = data.get("pages") or []
    snippets: list[str] = []

    for page in pages[:max_results]:
        title = (page.get("title") or "").strip()
        if not title:
            continue

        summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title)}"
        try:
            summary_resp = await client.get(summary_url)
            summary_resp.raise_for_status()
            summary_data = summary_resp.json()
        except Exception:
            continue

        extract = (summary_data.get("extract") or "").strip()
        if extract:
            snippets.append(f"Wikipedia ({title}): {extract}")

    return snippets


def _strip_tags(text: str) -> str:
    no_tags = re.sub(r"<[^>]+>", " ", text)
    no_entities = (
        no_tags.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    return re.sub(r"\s+", " ", no_entities).strip()

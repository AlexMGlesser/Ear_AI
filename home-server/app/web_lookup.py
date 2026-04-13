from __future__ import annotations

from urllib.parse import parse_qs, quote, unquote, urlparse
import html
import re
from pathlib import Path
import httpx

from .config import settings


LOOKUP_LOG_PATH = Path("logs/web_lookup.log")


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
        "are you there",
        "can you hear me",
        "do you hear me",
    )
    if any(text.strip() == phrase for phrase in small_talk):
        return False

    non_web_intents = (
        "how many d",
        "damage",
        "spell",
        "roll if i cast",
        "math",
        "calculate",
        "convert",
    )
    if any(token in text for token in non_web_intents):
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

    # Only auto-lookup question forms when they are clearly time-sensitive.
    time_sensitive_starts = (
        "what is the latest",
        "what's the latest",
        "what is current",
        "what's current",
        "what happened today",
        "what is the weather",
        "what's the weather",
        "is it raining",
        "will it rain",
        "what is the price",
        "what's the price",
        "what is the stock",
        "what's the stock",
    )
    normalized = text.strip()
    return normalized.startswith(time_sensitive_starts)


def needs_lookup_clarification(user_text: str) -> str:
    text = user_text.lower().strip()

    if "weather" in text and not _contains_location(text):
        return "Which city or area do you want the weather for?"

    if any(token in text for token in ("news", "latest", "current update")) and not _contains_subject(text):
        return "What topic do you want me to look up?"

    if any(token in text for token in ("look up", "search", "internet", "find")) and not _contains_subject(text):
        return "What do you want me to look up?"

    return ""


def direct_lookup_meta_response(user_text: str) -> str:
    text = user_text.lower().strip()

    if any(
        phrase in text
        for phrase in (
            "do you have internet access",
            "can you access the internet",
            "are you connected to the internet",
            "can you go on the internet",
        )
    ):
        return (
            "Yes. I can do read-only internet lookups through your home server when needed, "
            "but I cannot buy things or interact with sites beyond reading information."
        )

    if any(
        phrase in text
        for phrase in (
            "can you browse the web",
            "can you search the web",
            "can you look things up online",
        )
    ):
        return (
            "Yes. I can search and read information from the web through your home server, "
            "but only in a read-only way."
        )

    return ""


def direct_time_response(user_text: str, now_utc_iso: str) -> str:
    text = user_text.lower().strip()

    date_triggers = (
        "today's date",
        "todays date",
        "what is the date",
        "what's the date",
        "current date",
    )
    time_triggers = (
        "current utc date and time",
        "utc date and time",
        "current utc time",
        "utc time",
        "what time is it",
        "current time",
    )

    if any(trigger in text for trigger in date_triggers):
        return f"Today's UTC date is {now_utc_iso[:10]}."

    if any(trigger in text for trigger in time_triggers):
        return f"Current UTC date and time is {now_utc_iso}."

    return ""


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

        # Fallback: DuckDuckGo Instant Answer API for environments where HTML POST is blocked.
        if not snippets:
            instant = await _fetch_duckduckgo_instant(client, query, settings.web_lookup_max_results)
            if instant:
                snippets.extend(instant)

        # Fallback: DuckDuckGo lite GET endpoint.
        if not snippets:
            lite = await _fetch_duckduckgo_lite(client, query, settings.web_lookup_max_results)
            if lite:
                snippets.extend(lite)

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
    top_results: list[tuple[str, str, str]] = []
    # Extract title/snippet pairs from DDG HTML response.
    title_pattern = re.compile(
        r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    snippet_pattern = re.compile(
        r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>|<div[^>]*class="result__snippet"[^>]*>(.*?)</div>',
        re.IGNORECASE | re.DOTALL,
    )

    title_matches = title_pattern.findall(html)
    raw_snippets = snippet_pattern.findall(html)
    parsed_snippets = [_strip_tags(a or b) for a, b in raw_snippets]

    for idx, (href, title_html) in enumerate(title_matches[:max_results]):
        title = _strip_tags(title_html)
        snippet = parsed_snippets[idx] if idx < len(parsed_snippets) else ""
        url = _normalize_ddg_result_url(href)
        top_results.append((title, url, snippet))
        if snippet:
            snippets.append(f"DuckDuckGo ({title}) [{url}]: {snippet}")
        elif title:
            snippets.append(f"DuckDuckGo ({title}) [{url}]")

    if settings.web_lookup_fetch_top_pages:
        for title, url, _ in top_results[: settings.web_lookup_page_count]:
            excerpt = await _fetch_page_excerpt(client, url, settings.web_lookup_page_excerpt_chars)
            if excerpt:
                snippets.append(f"Page ({title}) [{url}]: {excerpt}")

    return snippets


async def _fetch_duckduckgo_instant(
    client: httpx.AsyncClient,
    query: str,
    max_results: int,
) -> list[str]:
    url = "https://api.duckduckgo.com/"
    try:
        response = await client.get(
            url,
            params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
            headers={"User-Agent": "EarAI-HomeServer/1.0"},
        )
        response.raise_for_status()
        data = response.json()
    except Exception:
        return []

    snippets: list[str] = []

    abstract = (data.get("AbstractText") or "").strip()
    abstract_url = (data.get("AbstractURL") or "").strip()
    heading = (data.get("Heading") or "").strip() or "Instant Answer"
    if abstract:
        if abstract_url:
            snippets.append(f"DuckDuckGo Instant ({heading}) [{abstract_url}]: {abstract}")
        else:
            snippets.append(f"DuckDuckGo Instant ({heading}): {abstract}")

    related = data.get("RelatedTopics") or []
    for item in related:
        if len(snippets) >= max_results:
            break

        if isinstance(item, dict) and "Topics" in item:
            for nested in item.get("Topics") or []:
                if len(snippets) >= max_results:
                    break
                text = (nested.get("Text") or "").strip() if isinstance(nested, dict) else ""
                first_url = (nested.get("FirstURL") or "").strip() if isinstance(nested, dict) else ""
                if text:
                    if first_url:
                        snippets.append(f"DuckDuckGo Instant [{first_url}]: {text}")
                    else:
                        snippets.append(f"DuckDuckGo Instant: {text}")
            continue

        text = (item.get("Text") or "").strip() if isinstance(item, dict) else ""
        first_url = (item.get("FirstURL") or "").strip() if isinstance(item, dict) else ""
        if text:
            if first_url:
                snippets.append(f"DuckDuckGo Instant [{first_url}]: {text}")
            else:
                snippets.append(f"DuckDuckGo Instant: {text}")

    return snippets[:max_results]


async def _fetch_duckduckgo_lite(
    client: httpx.AsyncClient,
    query: str,
    max_results: int,
) -> list[str]:
    url = "https://lite.duckduckgo.com/lite/"
    try:
        response = await client.get(
            url,
            params={"q": query},
            headers={"User-Agent": "EarAI-HomeServer/1.0"},
        )
        response.raise_for_status()
        html = response.text
    except Exception:
        return []

    link_pattern = re.compile(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
    snippets: list[str] = []

    for href, title_html in link_pattern.findall(html):
        title = _strip_tags(title_html)
        if not title:
            continue

        normalized = _normalize_ddg_result_url(href)
        if normalized.startswith("https://duckduckgo.com/l/"):
            continue

        snippets.append(f"DuckDuckGo Lite ({title}) [{normalized}]")
        if len(snippets) >= max_results:
            break

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


async def _fetch_page_excerpt(client: httpx.AsyncClient, url: str, max_chars: int) -> str:
    try:
        response = await client.get(url, follow_redirects=True, headers={"User-Agent": "EarAI-HomeServer/1.0"})
        response.raise_for_status()
        html = response.text
    except Exception:
        return ""

    # Remove non-content blocks before extracting text.
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r"<noscript.*?</noscript>", " ", html, flags=re.IGNORECASE | re.DOTALL)

    paragraphs = re.findall(r"<(?:p|article|main|section)[^>]*>(.*?)</(?:p|article|main|section)>", html, flags=re.IGNORECASE | re.DOTALL)
    text_chunks = [_strip_tags(chunk) for chunk in paragraphs]
    text_chunks = [chunk for chunk in text_chunks if len(chunk) > 60]

    if not text_chunks:
        body_match = re.search(r"<body[^>]*>(.*?)</body>", html, flags=re.IGNORECASE | re.DOTALL)
        if body_match:
            body_text = _strip_tags(body_match.group(1))
            body_text = re.sub(r"\s+", " ", body_text).strip()
            return _truncate_sentence(body_text, max_chars)
        return ""

    combined = " ".join(text_chunks[:3])
    combined = re.sub(r"\s+", " ", combined).strip()
    return _truncate_sentence(combined, max_chars)


def _contains_location(text: str) -> bool:
    location_hints = (
        " in ",
        " for ",
        " near ",
        " at ",
        " seattle",
        "new york",
        "london",
        "home",
        "here",
    )
    return any(hint in text for hint in location_hints)


def _contains_subject(text: str) -> bool:
    generic_phrases = {
        "look up",
        "search",
        "internet",
        "find",
        "look this up",
        "search this",
        "something",
        "stuff",
        "some internet searches",
        "the internet",
    }

    stripped = re.sub(r"[^a-z0-9\s]", " ", text)
    stripped = re.sub(r"\s+", " ", stripped).strip()

    if stripped in generic_phrases:
        return False

    words = [word for word in stripped.split() if word not in {"can", "you", "please", "me", "up", "the", "a", "an", "for"}]
    return len(words) >= 3


def _normalize_ddg_result_url(href: str) -> str:
    if not href:
        return ""

    candidate = href.strip()
    if candidate.startswith("//"):
        candidate = f"https:{candidate}"
    elif candidate.startswith("/"):
        candidate = f"https://duckduckgo.com{candidate}"

    parsed = urlparse(candidate)
    query = parse_qs(parsed.query)
    uddg = query.get("uddg", [])
    if uddg:
        return unquote(uddg[0])

    return candidate


def looks_generic_or_unverified(answer: str) -> bool:
    text = answer.lower().strip()
    generic_markers = (
        "as of my last update",
        "i cannot verify",
        "for the most current information",
        "check sources",
        "no specific major announcements",
        "i am not sure",
        "i do not know",
        "one moment",
        "let me check",
        "give me a second",
    )
    return any(marker in text for marker in generic_markers)


def fallback_answer_from_web_context(web_context: str) -> str:
    items = parse_lookup_items(web_context)
    if not items:
        return "I could not retrieve internet results right now, so I cannot verify that yet."

    top = items[:2]
    fragments: list[str] = []
    for item in top:
        snippet = _truncate_sentence(item["snippet"], 160)
        fragments.append(_clean_spoken_snippet(snippet))

    return "Here is a quick summary: " + " ".join(fragment for fragment in fragments if fragment)


def parse_lookup_items(web_context: str) -> list[dict[str, str]]:
    lines = [line.strip() for line in web_context.splitlines() if line.strip().startswith("-")]
    parsed: list[dict[str, str]] = []

    pattern = re.compile(r"^-\s*(.*?)\s*\[(.*?)\]\s*:\s*(.*)$")
    fallback_pattern = re.compile(r"^-\s*(.*?)\s*:\s*(.*)$")

    for line in lines:
        match = pattern.match(line)
        if match:
            parsed.append(
                {
                    "source": match.group(1).strip(),
                    "url": match.group(2).strip(),
                    "snippet": match.group(3).strip(),
                }
            )
            continue

        alt = fallback_pattern.match(line)
        if alt:
            parsed.append(
                {
                    "source": alt.group(1).strip(),
                    "url": "",
                    "snippet": alt.group(2).strip(),
                }
            )

    return parsed


def log_lookup_result(query: str, web_context: str) -> None:
    items = parse_lookup_items(web_context)
    if not items:
        return

    LOOKUP_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    log_lines = [f"QUERY: {query}"]
    for item in items:
        source = item["source"]
        url = item["url"] or "(no-url)"
        snippet = item["snippet"]
        log_lines.append(f"- {source}")
        log_lines.append(f"  URL: {url}")
        log_lines.append(f"  SNIPPET: {snippet}")
    log_lines.append("-")

    LOOKUP_LOG_PATH.open("a", encoding="utf-8").write("\n".join(log_lines) + "\n")


def _truncate_sentence(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    shortened = text[:max_len].rsplit(" ", 1)[0].strip()
    return f"{shortened}..."


def _clean_spoken_snippet(text: str) -> str:
    cleaned = html.unescape(text)
    cleaned = re.sub(r"https?://\S+", "", cleaned)
    cleaned = re.sub(r"\b(reuters|duckduckgo|wikipedia|bloomberg|pcmag|accuweather|weather underground|the weather channel|national weather service)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+\.{2,}", ".", cleaned)
    cleaned = re.sub(r"\s+,", ",", cleaned)
    cleaned = re.sub(r"\s+\)", ")", cleaned)
    cleaned = re.sub(r"\(\s+", "(", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -:|")
    if cleaned and cleaned[-1] not in ".!?":
        cleaned = f"{cleaned}."
    return cleaned

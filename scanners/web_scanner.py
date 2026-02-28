"""
Web scanner — scrapes Paraguayan websites to find businesses by keywords,
using an LLM via OpenRouter for extraction. Mirrors original scanner.py.

Active sources (only those that work reliably):
  - paraguaypymes (static HTML)
  - duckduckgo, duckduckgo_startups (DDG Lite, no-JS)

Excluded: crunchbase (403), abc/ultima_hora/bing (JS-only), dinaem/innovando (timeout)
"""

import asyncio
import hashlib
import json
import logging
import os
import time
from typing import Any
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from models import Competitor, ScanResult, ScannerAnalysis
from scanners.base import BaseScanner

logger = logging.getLogger("validator.scanners.web")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)
_REQUEST_TIMEOUT = 15.0
_LLM_TIMEOUT = 5.0  # Aggressive timeout for LLM extraction to avoid blocking
_MAX_HTML_CHARS = 3000
_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

_SOURCE_DELAYS: dict[str, float] = {
    "duckduckgo": 5.0,
    "duckduckgo_startups": 5.0,
    "paraguaypymes": 2.0,
    "default": 1.5,
}

_SOURCE_LOCK_GROUP: dict[str, str] = {
    "duckduckgo_startups": "duckduckgo",
}

_SOURCES: dict[str, str] = {
    "paraguaypymes": "https://paraguaypymes.com/search.php?q={keyword}",
    "duckduckgo": "https://lite.duckduckgo.com/lite/?q={keyword}+empresa+paraguay",
    "duckduckgo_startups": "https://lite.duckduckgo.com/lite/?q={keyword}+startup+asuncion+paraguay",
}

_http_semaphore: asyncio.Semaphore | None = None
_llm_semaphore: asyncio.Semaphore | None = None
_LLM_CACHE_TTL = 900  # 15 minutes
_llm_cache: dict[str, tuple[list[dict[str, Any]], float]] = {}


def _get_http_semaphore() -> asyncio.Semaphore:
    global _http_semaphore
    if _http_semaphore is None:
        _http_semaphore = asyncio.Semaphore(5)
    return _http_semaphore


def _get_llm_semaphore() -> asyncio.Semaphore:
    global _llm_semaphore
    if _llm_semaphore is None:
        _llm_semaphore = asyncio.Semaphore(3)
    return _llm_semaphore


_FULL_STRIP_TAGS = {
    "script", "style", "nav", "footer", "head", "iframe",
    "header", "aside", "form", "button", "noscript", "svg",
}

_EXTRACTION_PROMPT = """\
You are a business data extractor specialized in companies operating in Paraguay.

From the following web content scraped from "{source_name}", extract ALL companies, startups, or businesses that are related to the topic: "{keywords}".

Rules:
- Include any company that operates in Paraguay, serves Paraguayan customers, or is mentioned in a Paraguayan business context — even if not explicitly labeled as "Paraguayan"
- The search was already filtered for Paraguay, so trust the context: if a company appears in these results, it is likely relevant
- Extract the company name, a 1-2 sentence description of what they do, and any URL you can find
- Ignore navigation links, social media accounts, news article titles, and generic directory listings that mention no specific company
- If no specific companies are found, return an empty array
- Do NOT invent or hallucinate company names
- Respond ONLY with a valid JSON array, no extra text

Response format:
[
  {{"name": "...", "description": "...", "url": "..."}}
]

Content:
{html_content}
"""


# ---------------------------------------------------------------------------
# HTML cleaning
# ---------------------------------------------------------------------------

def _clean_html(raw_html: str) -> str:
    soup = BeautifulSoup(raw_html, "lxml")

    for tag in soup.find_all(_FULL_STRIP_TAGS):
        tag.decompose()

    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        text = a.get_text(" ", strip=True)
        if text and href:
            a.replace_with(f"{text} [href={href}]")

    raw_text = soup.get_text(separator="\n", strip=True)

    lines: list[str] = []
    seen: set[str] = set()
    for line in raw_text.splitlines():
        line = line.strip()
        if len(line) < 3 or line in seen:
            continue
        seen.add(line)
        lines.append(line)

    return "\n".join(lines)[:_MAX_HTML_CHARS]


# ---------------------------------------------------------------------------
# Keyword expansion
# ---------------------------------------------------------------------------

def _expand_keywords(keywords: list[str]) -> list[str]:
    if not keywords:
        return []

    seen: set[str] = set()
    result: list[str] = []

    def _add(q: str) -> None:
        q = q.strip()
        if q and q not in seen:
            seen.add(q)
            result.append(q)

    for kw in keywords:
        _add(kw)

    if len(keywords) > 1:
        _add(" ".join(keywords))

    if len(keywords) > 2:
        anchor = keywords[0]
        for kw in keywords[1:]:
            _add(f"{anchor} {kw}")

    return result


# ---------------------------------------------------------------------------
# Internal async helpers
# ---------------------------------------------------------------------------

async def _fetch_source(
    client: httpx.AsyncClient,
    source_key: str,
    url: str,
) -> str:
    sem = _get_http_semaphore()
    async with sem:
        try:
            logger.info("Fetching source '%s' → %s", source_key, url)
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            if response.status_code != 200:
                logger.warning(
                    "Non-200 response (%d) for source '%s' — likely CAPTCHA/block",
                    response.status_code, source_key,
                )
                return ""
            logger.info("Completed fetch for '%s' (status %d)", source_key, response.status_code)
            return response.text
        except httpx.TimeoutException:
            logger.warning("Timeout fetching source '%s' at %s", source_key, url)
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "HTTP error %d for source '%s' at %s",
                exc.response.status_code, source_key, url,
            )
        except httpx.RequestError as exc:
            logger.warning("Request error for source '%s': %s", source_key, exc)
        return ""


def _llm_cache_key(source_key: str, keyword: str, html_content: str) -> str:
    h = hashlib.sha256(html_content.encode()[:2000]).hexdigest()[:16]
    return f"{source_key}:{keyword}:{h}"


async def _call_llm(
    client: httpx.AsyncClient,
    api_key: str,
    model: str,
    source_key: str,
    keyword: str,
    html_content: str,
) -> list[dict[str, Any]]:
    cache_key = _llm_cache_key(source_key, keyword, html_content)
    now = time.monotonic()
    if cache_key in _llm_cache:
        cached, ts = _llm_cache[cache_key]
        if now - ts < _LLM_CACHE_TTL:
            return cached
        del _llm_cache[cache_key]

    prompt = _EXTRACTION_PROMPT.format(
        source_name=source_key,
        keywords=keyword,
        html_content=html_content,
    )
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 2000,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://paraguay-startup-validator.com",
        "X-Title": "Paraguay Startup Validator",
    }

    sem = _get_llm_semaphore()
    async with sem:
        try:
            resp = await client.post(
                _OPENROUTER_URL, json=payload, headers=headers, timeout=_LLM_TIMEOUT,
            )
            resp.raise_for_status()
        except httpx.TimeoutException:
            logger.warning("LLM call timed out for source '%s', keyword '%s'", source_key, keyword)
            return []
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:400]
            logger.warning(
                "LLM HTTP error %d for source '%s', keyword '%s' — %s",
                exc.response.status_code, source_key, keyword, body,
            )
            return []
        except httpx.RequestError as exc:
            logger.warning("LLM request error for source '%s': %s", source_key, exc)
            return []

    try:
        data = resp.json()
        raw_text: str = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as exc:
        logger.warning("Unexpected LLM response structure for '%s': %s", source_key, exc)
        return []

    raw_text = raw_text.strip()
    # Strip markdown code blocks if present
    if raw_text.startswith("```"):
        for prefix in ("```json", "```"):
            if raw_text.startswith(prefix):
                raw_text = raw_text[len(prefix) :].lstrip()
                break
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3].rstrip()

    try:
        extracted: list[dict[str, Any]] = json.loads(raw_text)
        if not isinstance(extracted, list):
            raise ValueError("Expected a JSON array")
        _llm_cache[cache_key] = (extracted, now)
        return extracted
    except (json.JSONDecodeError, ValueError):
        pass

    # Salvage truncated JSON: find last complete object and close the array
    try:
        last_close = raw_text.rfind("}")
        if last_close != -1:
            salvaged = raw_text[: last_close + 1].rstrip().rstrip(",") + "]"
            extracted = json.loads(salvaged)
            if isinstance(extracted, list):
                logger.warning("Truncated LLM JSON salvaged for '%s' (%d entries)", source_key, len(extracted))
                _llm_cache[cache_key] = (extracted, now)
                return extracted
    except (json.JSONDecodeError, ValueError):
        pass

    logger.warning(
        "Failed to parse LLM JSON for '%s', keyword '%s' — raw: %.200s",
        source_key, keyword, raw_text,
    )
    return []


async def _scan_one(
    client: httpx.AsyncClient,
    source_key: str,
    url_template: str,
    keyword: str,
    api_key: str,
    model: str,
    domain_locks: dict[str, asyncio.Lock],
) -> list[dict[str, Any]]:
    url = url_template.replace("{keyword}", quote_plus(keyword))
    delay = _SOURCE_DELAYS.get(source_key, _SOURCE_DELAYS["default"])
    lock_key = _SOURCE_LOCK_GROUP.get(source_key, source_key)
    lock = domain_locks.setdefault(lock_key, asyncio.Lock())

    async with lock:
        raw_html = await _fetch_source(client, source_key, url)
        if raw_html:
            await asyncio.sleep(delay)

    if not raw_html:
        return []

    cleaned = _clean_html(raw_html)
    if not cleaned.strip():
        logger.info("No relevant content after HTML cleaning for source '%s', keyword '%s'", source_key, keyword)
        return []

    businesses = await _call_llm(client, api_key, model, source_key, keyword, cleaned)

    results: list[dict[str, Any]] = []
    for biz in businesses:
        if not isinstance(biz, dict):
            continue
        name = str(biz.get("name", "")).strip()
        if not name:
            continue
        results.append({
            "name": name,
            "description": str(biz.get("description", "")).strip(),
            "source": source_key,
            "url": str(biz.get("url", url)).strip() or url,
            "keyword_match": keyword,
        })

    return results


def _deduplicate(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for entry in entries:
        key = entry["name"].lower().strip()
        if key not in best or len(entry.get("description", "")) > len(best[key].get("description", "")):
            best[key] = entry
    return list(best.values())


# ---------------------------------------------------------------------------
# Scanner class
# ---------------------------------------------------------------------------

class WebScanner(BaseScanner):
    name = "Web PY"
    tier = "deep"
    weight = 30
    signal_direction = "positive"
    requires_env = ["OPENROUTER_API_KEY"]
    display_label = "Búsqueda Web PY"

    def __init__(self) -> None:
        super().__init__()
        # Store base client for cleanup (BaseScanner creates one we replace)
        self._base_client = self.client
        # Override with web-scraping-friendly settings
        self.client = httpx.AsyncClient(
            timeout=_REQUEST_TIMEOUT,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept-Language": "es-PY,es;q=0.9,en;q=0.8",
            },
            follow_redirects=True,
        )

    async def __aexit__(self, *args):
        """Close both our client and the base client we replaced."""
        try:
            await self.client.aclose()
        finally:
            await self._base_client.aclose()

    async def scan(self, keywords: list[str]) -> ScanResult:
        api_key = os.getenv("OPENROUTER_API_KEY", "")
        if not api_key:
            return ScanResult(
                source=self.name,
                available=False,
                hints=["OPENROUTER_API_KEY no configurada"],
            )

        model = os.getenv("WEB_SCANNER_MODEL", "anthropic/claude-3.5-sonnet")

        try:
            global _http_semaphore, _llm_semaphore
            _http_semaphore = asyncio.Semaphore(5)
            _llm_semaphore = asyncio.Semaphore(3)

            expanded = _expand_keywords(keywords)
            logger.info("Keywords expanded: %s → %s", keywords, expanded)

            domain_locks: dict[str, asyncio.Lock] = {}

            tasks = [
                _scan_one(
                    client=self.client,
                    source_key=src_key,
                    url_template=url_tpl,
                    keyword=kw,
                    api_key=api_key,
                    model=model,
                    domain_locks=domain_locks,
                )
                for kw in expanded
                for src_key, url_tpl in _SOURCES.items()
            ]

            logger.info(
                "Starting scan: %d expanded queries × %d source(s) = %d tasks",
                len(expanded), len(_SOURCES), len(tasks),
            )

            nested: list[list[dict[str, Any]]] = await asyncio.gather(*tasks)
            flat = [entry for sublist in nested for entry in sublist]
            unique = _deduplicate(flat)

            logger.info(
                "Scan complete. Raw results: %d — After deduplication: %d",
                len(flat), len(unique),
            )

            competitors = [
                Competitor(
                    name=biz["name"],
                    source=f"Web/{biz['source']}",
                    detail=biz.get("description", ""),
                    url=biz.get("url"),
                )
                for biz in unique
            ]

            count = len(unique)
            hints: list[str] = []
            if count > 10:
                hints.append(
                    f"{count} empresas/startups encontradas en la web paraguaya — sector con actividad visible"
                )
            elif count == 0:
                hints.append(
                    "Sin empresas detectables en la web paraguaya para este sector"
                )

            return ScanResult(
                source=self.name,
                count=count,
                competitors=competitors[:10],
                raw_signal=min(count / 15, 1.0),
                hints=hints,
            )

        except Exception as exc:
            logger.exception("WebScanner failed: %s", exc)
            return ScanResult(source=self.name, available=False, hints=[str(exc)])

    @classmethod
    def analyze(cls, result: ScanResult, score: int) -> ScannerAnalysis:
        a = ScannerAnalysis()
        if not result.available:
            return a

        c = result.count
        if c == 0:
            a.strengths.append(
                "Sin presencia web detectable de competidores — oportunidad de ser el primero visible online"
            )
            a.action_items.append(
                "Creá presencia web básica (landing + redes) antes de lanzar: en este sector serías el primero"
            )
        elif c <= 5:
            a.strengths.append(
                f"Solo {c} competidor(es) visible(s) en la web — baja saturación digital"
            )
        elif c <= 15:
            a.strengths.append(
                f"{c} competidores encontrados en la web — sector con actividad moderada y espacio para diferenciarse"
            )
        else:
            a.weaknesses.append(
                f"{c} competidores detectados en búsquedas web — alta visibilidad del sector online"
            )
            a.action_items.append(
                "Analizá los competidores web encontrados y buscá un ángulo que ninguno cubra bien"
            )

        return a

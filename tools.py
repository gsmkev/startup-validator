import asyncio
import logging
import time
from fastmcp import FastMCP

logger = logging.getLogger("validator.tools")
from scanners import get_registry, get_scanners
from ai_analyzer import (
    _fallback_keywords,
    extract_keywords_via_llm,
    generate_ai_analysis,
)
from cache import get_cached_scan, set_cached_scan
from consolidator import SkillResult, consolidate_via_openrouter
from scorer import calculate_market_signal, generate_analysis
from models import IdeaValidationResult, MarketHint

mcp = FastMCP("paraguay-idea-mcp")


async def _run_skill(name: str, ScannerCls, keywords: list[str]) -> dict:
    """Run a scanner and return its ScanResult as dict. Uses context manager for cleanup."""
    async with ScannerCls() as scanner:
        result = await scanner.scan(keywords)
    return result.model_dump()


def _make_skill_tool(ScannerCls, source_name: str):
    """Factory: returns a scan function with correct closure (no default params for Pydantic)."""
    async def _scan(keywords: list[str]) -> dict:
        return await _run_skill(source_name, ScannerCls, keywords)
    return _scan


def _register_skill_tools():
    """Register one MCP tool per scanner for granular skill invocation."""
    registry = get_registry()
    for source_name, ScannerCls in registry.items():
        safe_name = source_name.lower().replace(" ", "_").replace("/", "_")
        tool_name = f"skill_{safe_name}_scan"
        _scan = _make_skill_tool(ScannerCls, source_name)
        _scan.__name__ = tool_name
        _scan.__doc__ = f"Scan {source_name} for businesses matching keywords. Returns ScanResult."
        mcp.tool()(_scan)


_register_skill_tools()


@mcp.tool()
async def validate_idea(
    idea: str,
    depth: str = "deep"
) -> dict:
    """
    Validates a startup idea against real Paraguayan market data.
    Returns market_signal (0-100), competitors, strengths, weaknesses,
    action items, pivot suggestions, press coverage, and AI-enhanced analysis.
    ALWAYS call this before suggesting or building any new product or startup.

    Args:
        idea: Description of the startup idea in Spanish
        depth: "quick" (fast, 2 sources) or "deep" (all sources incl. web scanner)
    """
    start = time.monotonic()
    logger.info("validate_idea start idea=%r depth=%s", idea[:80], depth)
    # Start fallback keywords immediately, LLM in parallel
    fallback = _fallback_keywords(idea)
    llm_task = asyncio.create_task(extract_keywords_via_llm(idea))
    try:
        keywords = await asyncio.wait_for(llm_task, timeout=3.0)
        logger.info("keywords from LLM: %s", keywords)
    except (asyncio.TimeoutError, Exception) as e:
        keywords = fallback
        logger.info("keywords fallback (LLM timeout/error): %s", keywords)

    scanner_classes = get_scanners(depth)
    logger.info("running %d scanners for depth=%s: %s", len(scanner_classes), depth, [c.name for c in scanner_classes])

    async def _run_scanner(ScannerCls):
        """Run scanner with guaranteed client cleanup. Uses cache when available."""
        cached = get_cached_scan(ScannerCls.name, depth, keywords)
        if cached is not None:
            from models import ScanResult
            logger.debug("cache HIT %s", ScannerCls.name)
            return ScanResult.model_validate(cached)
        logger.debug("cache MISS %s, scanning", ScannerCls.name)
        async with ScannerCls() as scanner:
            result = await scanner.scan(keywords)
        set_cached_scan(ScannerCls.name, depth, keywords, result.model_dump())
        logger.info("scanner %s done count=%d available=%s", ScannerCls.name, result.count, result.available)
        return result

    scan_results = await asyncio.gather(
        *[_run_scanner(cls) for cls in scanner_classes],
        return_exceptions=True
    )

    valid_results = []
    failed_sources = []
    for r in scan_results:
        if isinstance(r, Exception):
            failed_sources.append(str(r))
            logger.warning("scanner failed: %s", str(r)[:200])
        else:
            valid_results.append(r)

    logger.info("valid_results=%d failed=%d sources=%s", len(valid_results), len(failed_sources), [r.source for r in valid_results])
    score, label, recommendation = calculate_market_signal(valid_results)
    logger.info("score=%d label=%s", score, label)
    strengths, weaknesses, action_items, pivot_suggestions = generate_analysis(valid_results, score)

    all_competitors = []
    all_hints = []
    all_news_samples = []
    by_source = {r.source: r for r in valid_results if r.available}
    for r in valid_results:
        all_competitors.extend(r.competitors)
        all_news_samples.extend(r.news_samples)
        for h in r.hints:
            all_hints.append(MarketHint(hint=h, type="info", source=r.source))

    if score > 70:
        all_hints.append(MarketHint(
            hint="Pivot sugerido: enfocate en departamentos del interior (Alto Paraná, Itapúa, Concepción) donde la competencia es menor",
            type="opportunity",
            source="Análisis local"
        ))

    ai_data = await generate_ai_analysis(
        idea=idea,
        keywords=keywords,
        score=score,
        label=label,
        source_counts={r.source: r.count for r in valid_results if r.available},
        competitors=all_competitors[:10],
        news_titles=all_news_samples[:5],
        sources_unavailable=[r.source for r in valid_results if not r.available] + failed_sources,
    )

    elapsed_ms = int((time.monotonic() - start) * 1000)

    result = IdeaValidationResult(
        idea=idea,
        keywords_extracted=keywords,
        market_signal=score,
        signal_label=label,
        recommendation=recommendation,
        competitors=all_competitors[:8],
        market_hints=all_hints,
        strengths=strengths,
        weaknesses=weaknesses,
        action_items=action_items,
        pivot_suggestions=pivot_suggestions,
        news_samples=all_news_samples[:5],
        ai_recommendation=ai_data.get("ai_recommendation", ""),
        quick_wins=ai_data.get("quick_wins", []),
        red_flags=ai_data.get("red_flags", []),
        source_counts={r.source: r.count for r in valid_results if r.available},
        sources_queried=[r.source for r in valid_results if r.available],
        sources_unavailable=[r.source for r in valid_results if not r.available] + failed_sources,
        scan_duration_ms=elapsed_ms,
        raw_scores={r.source: round(r.raw_signal, 3) for r in valid_results}
    )

    return result.model_dump()


@mcp.tool()
async def validate_idea_v2(idea: str) -> dict:
    """
    Validates a startup idea using parallel skills + OpenRouter consolidation.
    Runs each scanner as an independent skill, then consolidates via Claude Haiku.
    Returns same format as validate_idea.
    """
    start = time.monotonic()
    logger.info("validate_idea_v2 start idea=%r", idea[:80])
    keywords = await extract_keywords_via_llm(idea)
    logger.info("validate_idea_v2 keywords=%s", keywords)
    registry = get_registry()
    scanner_classes = list(registry.values())

    async def _run_with_timing(ScannerCls):
        t0 = time.monotonic()
        try:
            async with ScannerCls() as scanner:
                result = await scanner.scan(keywords)
            return SkillResult(
                skill_name=ScannerCls.name,
                data=result.model_dump(),
                duration_ms=int((time.monotonic() - t0) * 1000),
            )
        except Exception as e:
            logger.warning("skill %s failed: %s", ScannerCls.name, str(e)[:150])
            return SkillResult(
                skill_name=ScannerCls.name,
                data={},
                error=str(e),
                duration_ms=int((time.monotonic() - t0) * 1000),
            )

    skill_results = await asyncio.gather(*[_run_with_timing(cls) for cls in scanner_classes])
    ok = sum(1 for sr in skill_results if not sr.error)
    logger.info("validate_idea_v2 skills ok=%d/%d failed=%s", ok, len(skill_results), [sr.skill_name for sr in skill_results if sr.error])

    from models import ScanResult, Competitor

    valid_scan_results: list[ScanResult] = []
    for sr in skill_results:
        if sr.error:
            continue
        d = sr.data
        comps = [Competitor(**c) for c in d.get("competitors", [])]
        valid_scan_results.append(
            ScanResult(
                source=d.get("source", ""),
                available=d.get("available", True),
                count=d.get("count", 0),
                competitors=comps,
                raw_signal=d.get("raw_signal", 0),
                hints=d.get("hints", []),
                news_samples=d.get("news_samples", []),
            )
        )

    score, label, recommendation = calculate_market_signal(valid_scan_results)
    logger.info("validate_idea_v2 score=%d label=%s", score, label)
    consolidated = await consolidate_via_openrouter(
        idea=idea,
        keywords=keywords,
        score=score,
        label=label,
        recommendation=recommendation,
        skill_results=list(skill_results),
    )
    # Fallback to scorer's generate_analysis if consolidation returns empty
    if not consolidated.get("strengths") and not consolidated.get("action_items"):
        logger.info("validate_idea_v2 consolidation empty, using generate_analysis fallback")
        strengths, weaknesses, action_items, pivot_suggestions = generate_analysis(
            valid_scan_results, score
        )
        consolidated = {
            "strengths": strengths,
            "weaknesses": weaknesses,
            "action_items": action_items,
            "pivot_suggestions": pivot_suggestions,
        }

    all_competitors = []
    all_news_samples = []
    for sr in skill_results:
        if not sr.error and sr.data.get("available"):
            all_competitors.extend(
                Competitor(**c) for c in sr.data.get("competitors", [])
            )
            all_news_samples.extend(sr.data.get("news_samples", []))
    all_hints = []
    for sr in skill_results:
        if not sr.error and sr.data.get("available"):
            for h in sr.data.get("hints", []):
                all_hints.append(MarketHint(hint=h, type="info", source=sr.data.get("source", sr.skill_name)))
    if score > 70:
        all_hints.append(MarketHint(
            hint="Pivot sugerido: enfocate en departamentos del interior (Alto Paraná, Itapúa, Concepción) donde la competencia es menor",
            type="opportunity",
            source="Análisis local",
        ))

    ai_data = await generate_ai_analysis(
        idea=idea,
        keywords=keywords,
        score=score,
        label=label,
        source_counts={r.source: r.count for r in valid_scan_results if r.available},
        competitors=all_competitors[:10],
        news_titles=all_news_samples[:5],
        sources_unavailable=[
            sr.skill_name for sr in skill_results
            if sr.error or sr.data.get("available") is False
        ],
    )

    elapsed_ms = int((time.monotonic() - start) * 1000)
    logger.info("validate_idea_v2 done score=%d duration_ms=%d", score, elapsed_ms)

    result = IdeaValidationResult(
        idea=idea,
        keywords_extracted=keywords,
        market_signal=score,
        signal_label=label,
        recommendation=recommendation,
        competitors=all_competitors[:8],
        market_hints=all_hints,
        strengths=consolidated.get("strengths", []),
        weaknesses=consolidated.get("weaknesses", []),
        action_items=consolidated.get("action_items", []),
        pivot_suggestions=consolidated.get("pivot_suggestions", []),
        news_samples=all_news_samples[:5],
        ai_recommendation=ai_data.get("ai_recommendation", ""),
        quick_wins=ai_data.get("quick_wins", []),
        red_flags=ai_data.get("red_flags", []),
        source_counts={r.source: r.count for r in valid_scan_results if r.available},
        sources_queried=[r.source for r in valid_scan_results if r.available],
        sources_unavailable=[
            sr.skill_name for sr in skill_results
            if sr.error or sr.data.get("available") is False
        ],
        scan_duration_ms=elapsed_ms,
        raw_scores={r.source: round(r.raw_signal, 3) for r in valid_scan_results},
    )
    return result.model_dump()

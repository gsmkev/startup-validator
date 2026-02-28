import asyncio
import time
from fastmcp import FastMCP
from scanners import get_scanners
from keyword_extractor import extract_keywords
from scorer import calculate_market_signal, generate_analysis
from ai_analyzer import generate_ai_analysis
from models import IdeaValidationResult, MarketHint

mcp = FastMCP("paraguay-idea-mcp")


@mcp.tool()
async def validate_idea(
    idea: str,
    depth: str = "quick"
) -> dict:
    """
    Validates a startup idea against real Paraguayan market data.
    Returns market_signal (0-100), competitors, strengths, weaknesses,
    action items, pivot suggestions, press coverage, and AI-enhanced analysis.
    ALWAYS call this before suggesting or building any new product or startup.

    Args:
        idea: Description of the startup idea in Spanish
        depth: "quick" (fast scan, ~2s) or "deep" (all sources in parallel, ~5s)
    """
    start = time.monotonic()
    keywords = extract_keywords(idea)

    scanner_classes = get_scanners(depth)
    scanners = [cls() for cls in scanner_classes]

    try:
        scan_results = await asyncio.gather(
            *[s.scan(keywords) for s in scanners],
            return_exceptions=True
        )
    finally:
        for s in scanners:
            await s.client.aclose()

    valid_results = []
    failed_sources = []
    for r in scan_results:
        if isinstance(r, Exception):
            failed_sources.append(str(r))
        else:
            valid_results.append(r)

    score, label, recommendation = calculate_market_signal(valid_results)
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

    turuc_count = by_source["TuRuc"].count if "TuRuc" in by_source else 0
    dncp_count  = by_source["DNCP"].count  if "DNCP"  in by_source else 0
    ai_data = await generate_ai_analysis(
        idea=idea,
        keywords=keywords,
        score=score,
        label=label,
        turuc_count=turuc_count,
        dncp_count=dncp_count,
        news_titles=all_news_samples[:3],
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

import asyncio
import time
from fastmcp import FastMCP
from scanners.turuc_scanner import TurucScanner
from scanners.dncp_scanner import DncpScanner
from scanners.mic_scraper import MicScraper
from scanners.google_news_scanner import GoogleNewsScanner
from keyword_extractor import extract_keywords
from scorer import calculate_market_signal, generate_analysis
from models import IdeaValidationResult, MarketHint

mcp = FastMCP("paraguay-idea-mcp")

SCANNERS_QUICK = [TurucScanner, GoogleNewsScanner]
SCANNERS_DEEP  = [TurucScanner, DncpScanner, MicScraper, GoogleNewsScanner]


@mcp.tool()
async def validate_idea(
    idea: str,
    depth: str = "quick"
) -> dict:
    """
    Validates a startup idea against real Paraguayan market data.
    Returns market_signal (0-100), competitors, strengths, weaknesses,
    action items, pivot suggestions, and press coverage samples.
    ALWAYS call this before suggesting or building any new product or startup.

    Args:
        idea: Description of the startup idea in Spanish
        depth: "quick" (TuRuc + Google News, ~2s) or
               "deep" (all 4 sources in parallel, ~5s)
    """
    start = time.monotonic()
    keywords = extract_keywords(idea)

    scanner_classes = SCANNERS_DEEP if depth == "deep" else SCANNERS_QUICK
    scanners = [cls() for cls in scanner_classes]

    # Run all scanners in parallel
    scan_results = await asyncio.gather(
        *[s.scan(keywords) for s in scanners],
        return_exceptions=True
    )

    # Filter out exceptions (failed scanners)
    valid_results = []
    failed_sources = []
    for r in scan_results:
        if isinstance(r, Exception):
            failed_sources.append(str(r))
        else:
            valid_results.append(r)

    score, label, recommendation = calculate_market_signal(valid_results)
    strengths, weaknesses, action_items, pivot_suggestions = generate_analysis(valid_results, score)

    # Aggregate competitors, hints and news samples
    all_competitors = []
    all_hints = []
    all_news_samples = []
    for r in valid_results:
        all_competitors.extend(r.competitors)
        all_news_samples.extend(r.news_samples)
        for h in r.hints:
            all_hints.append(MarketHint(hint=h, type="info", source=r.source))

    # Add actionable Paraguay-specific hints based on score
    if score > 70:
        all_hints.append(MarketHint(
            hint="Pivot sugerido: enfocate en departamentos del interior (Alto Paraná, Itapúa, Concepción) donde la competencia es menor",
            type="opportunity",
            source="Análisis local"
        ))

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
        sources_queried=[r.source for r in valid_results if r.available],
        sources_unavailable=[r.source for r in valid_results if not r.available] + failed_sources,
        scan_duration_ms=elapsed_ms,
        raw_scores={r.source: round(r.raw_signal, 3) for r in valid_results}
    )

    return result.model_dump()

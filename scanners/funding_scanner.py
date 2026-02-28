"""
Funding scanner — detects startups with investment in Paraguay/region.

Crunchbase and Dealroom often block scrapers (403/paywall). This scanner
tries public pages; when blocked, returns empty. Use API keys if available.
"""
import logging
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from models import Competitor, ScanResult, ScannerAnalysis
from scanners.base import BaseScanner

logger = logging.getLogger("validator.scanners.funding")

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36"
)


class FundingScanner(BaseScanner):
    name = "Funding PY"
    tier = "deep"
    weight = 10
    signal_direction = "positive"  # More funded startups = validated market
    display_label = "Funding PY"

    async def scan(self, keywords: list[str]) -> ScanResult:
        logger.info("scan keywords=%s", keywords[:2])
        competitors: list[Competitor] = []
        # Crunchbase typically returns 403 for unauthenticated bots
        # Try DuckDuckGo as proxy for "startup paraguay funding"
        try:
            query = quote_plus("startup paraguay " + " ".join(keywords[:2]) + " funding inversión")
            url = f"https://lite.duckduckgo.com/lite/?q={query}"
            resp = await self.client.get(
                url,
                timeout=6.0,
                headers={"User-Agent": _USER_AGENT},
                follow_redirects=True,
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            links = soup.select("a[href]")
            for a in links:
                href = a.get("href", "")
                text = a.get_text(strip=True)
                if (
                    ("crunchbase" in href or "dealroom" in href or "startup" in text.lower())
                    and len(text) > 4
                    and "duckduckgo" not in href
                ):
                    competitors.append(
                        Competitor(
                            name=text[:80],
                            source="Funding/DDG",
                            detail=" ".join(keywords[:2]),
                            url=href if href.startswith("http") else None,
                        )
                    )
            seen: set[str] = set()
            unique = []
            for c in competitors:
                k = c.name.lower()
                if k not in seen:
                    seen.add(k)
                    unique.append(c)
        except Exception as e:
            logger.debug("Funding scan failed: %s", e)
            unique = []

        count = len(unique)
        logger.info("Funding done count=%d", count)
        return ScanResult(
            source=self.name,
            count=count,
            competitors=unique[:5],
            raw_signal=min(count / 10, 1.0),
            hints=[f"{count} referencias a funding/startups en sector"] if count > 0 else [],
        )

    @classmethod
    def analyze(cls, result: ScanResult, score: int) -> ScannerAnalysis:
        a = ScannerAnalysis()
        if not result.available:
            return a
        if result.count > 0:
            a.strengths.append(
                "Señales de funding/startups en sector — validación por inversores"
            )
        return a

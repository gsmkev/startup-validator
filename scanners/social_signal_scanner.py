"""
Social signal scanner — measures demand/engagement on Paraguayan social platforms.

Uses DuckDuckGo Lite as proxy for social/paraguay business searches. Facebook
has aggressive anti-scraping; this provides best-effort signals.
"""
import logging
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from models import Competitor, ScanResult, ScannerAnalysis
from scanners.base import BaseScanner

logger = logging.getLogger("validator.scanners.social")

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
# Public search endpoints - may return login wall or limited data
_SOURCES = [
    ("Facebook Search", "https://www.facebook.com/public/{keyword}"),
]


class SocialSignalScanner(BaseScanner):
    name = "Social PY"
    tier = "deep"
    weight = 15
    signal_direction = "positive"
    display_label = "Redes Sociales PY"

    async def scan(self, keywords: list[str]) -> ScanResult:
        logger.info("scan keywords=%s", keywords[:2])
        total_signals = 0
        competitors: list[Competitor] = []

        for keyword in keywords[:2]:
            query = quote_plus(f"{keyword} Paraguay")
            try:
                url = f"https://lite.duckduckgo.com/lite/?q={query}+empresa+facebook+paraguay"
                resp = await self.client.get(
                    url,
                    timeout=5.0,
                    headers={"User-Agent": _USER_AGENT},
                    follow_redirects=True,
                )
                resp.raise_for_status()
                text = resp.text

                # DDG Lite returns HTML; count results mentioning social/paraguay
                soup = BeautifulSoup(text, "lxml")
                links = soup.select("a[href]")
                for a in links:
                    href = a.get("href", "")
                    text_lower = (a.get_text() + " " + href).lower()
                    if any(kw in text_lower for kw in [keyword.lower(), "paraguay", "facebook", "empresa"]):
                        total_signals += 1
                        name = a.get_text(strip=True)[:60]
                        if name and name not in ("Ver más", "Siguiente", "Anterior"):
                            competitors.append(
                                Competitor(
                                    name=name,
                                    source="Social/DuckDuckGo",
                                    detail=keyword,
                                    url=href if href.startswith("http") else None,
                                )
                            )

                # Deduplicate by name
                seen = set()
                unique = []
                for c in competitors:
                    if c.name.lower() not in seen:
                        seen.add(c.name.lower())
                        unique.append(c)
                competitors = unique[:10]

            except Exception as e:
                logger.debug("Social scan failed: %s", e)
                continue

        count = max(total_signals, len(competitors))
        logger.info("Social done count=%d", count)
        return ScanResult(
            source=self.name,
            count=min(count, 50),
            competitors=competitors[:8],
            raw_signal=min(count / 50, 1.0),
            hints=[f"{count} señales de actividad en redes/sector"] if count > 0 else [],
        )

    @classmethod
    def analyze(cls, result: ScanResult, score: int) -> ScannerAnalysis:
        a = ScannerAnalysis()
        if not result.available:
            return a
        c = result.count
        if c > 10:
            a.strengths.append(
                "Actividad visible en redes sociales paraguayas — sector con engagement"
            )
        elif c > 0:
            a.strengths.append(
                "Algunas señales de presencia en redes — mercado con tracción digital"
            )
        return a

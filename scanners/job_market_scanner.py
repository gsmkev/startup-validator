"""
Job market scanner — uses job board listings as proxy for sector growth.

More job postings in a sector = industry expanding (positive signal for opportunity).
Sources: Bumeran Paraguay, CompuTrabajo Paraguay.
"""
import logging
import re
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from models import Competitor, ScanResult, ScannerAnalysis
from scanners.base import BaseScanner

logger = logging.getLogger("validator.scanners.jobs")

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
_SOURCES = [
    ("Bumeran", "https://www.bumeran.com.py/empleos-busqueda-{keyword}.html"),
    ("CompuTrabajo", "https://www.computrabajo.com.py/ofertas-de-trabajo?q={keyword}"),
]


class JobMarketScanner(BaseScanner):
    name = "Jobs PY"
    tier = "deep"
    weight = 12
    signal_direction = "negative"  # More jobs = sector growing = opportunity
    display_label = "Empleos PY"

    async def scan(self, keywords: list[str]) -> ScanResult:
        logger.info("scan keywords=%s", keywords[:2])
        total_jobs = 0
        competitors: list[Competitor] = []
        hints: list[str] = []

        for keyword in keywords[:2]:
            kw_slug = quote_plus(keyword.replace(" ", "-"))
            for source_name, url_tpl in _SOURCES:
                try:
                    url = url_tpl.replace("{keyword}", kw_slug)
                    resp = await self.client.get(
                        url,
                        timeout=8.0,
                        headers={"User-Agent": _USER_AGENT},
                        follow_redirects=True,
                    )
                    resp.raise_for_status()
                    text = resp.text

                    if "bumeran" in url.lower():
                        # Bumeran: look for job count or listing items
                        soup = BeautifulSoup(text, "lxml")
                        items = soup.select(
                            ".job-item, .offer-item, [data-job], .listing-card, article"
                        )
                        count = len(items)
                        if count == 0:
                            # Fallback: regex for "X ofertas" or similar
                            m = re.search(r"(\d+)\s*(?:ofertas|empleos|vacantes)", text, re.I)
                            count = int(m.group(1)) if m else 0
                        total_jobs += count
                        for item in items[:3]:
                            title_el = item.select_one("h2, h3, .title, a[href*='empleo']")
                            if title_el:
                                name = title_el.get_text(strip=True)[:80]
                                if name:
                                    competitors.append(
                                        Competitor(
                                            name=name,
                                            source=f"Jobs/{source_name}",
                                            detail=keyword,
                                        )
                                    )

                    elif "computrabajo" in url.lower():
                        soup = BeautifulSoup(text, "lxml")
                        # "más de 99 ofertas" or similar
                        m = re.search(r"más de (\d+)|(\d+)\s*ofertas|(\d+)\s*empleos", text, re.I)
                        count = int(m.group(1) or m.group(2) or m.group(3) or 0)
                        if count == 0:
                            items = soup.select(
                                ".job-item, .offer, .iOfertas, [class*='offer'], [class*='job']"
                            )
                            count = len(items)
                        total_jobs += count
                        for a in soup.select('a[href*="/trabajo-"], a[href*="/empleo"]')[:3]:
                            name = a.get_text(strip=True)
                            if name and len(name) > 5 and name.lower() not in ("ver más", "ver detalles"):
                                competitors.append(
                                    Competitor(
                                        name=name[:80],
                                        source=f"Jobs/{source_name}",
                                        detail=keyword,
                                    )
                                )

                except Exception as e:
                    logger.debug("Jobs %s %r failed: %s", source_name, keyword, e)
                    continue

        logger.info("Jobs done total_jobs=%d", total_jobs)
        # raw_signal: negative = more jobs = opportunity. Cap at -0.3
        raw = -min(total_jobs / 50, 1.0) * 0.3 if total_jobs > 0 else 0.0
        if total_jobs > 0:
            hints.append(f"{total_jobs} ofertas de empleo en sector — industria en expansión")

        return ScanResult(
            source=self.name,
            count=total_jobs,
            competitors=competitors[:8],
            raw_signal=raw,
            hints=hints,
        )

    @classmethod
    def analyze(cls, result: ScanResult, score: int) -> ScannerAnalysis:
        a = ScannerAnalysis()
        if not result.available:
            return a
        c = result.count
        if c > 20:
            a.strengths.append(
                f"{c} ofertas de empleo en el sector — señal de industria en crecimiento"
            )
        elif c > 0:
            a.strengths.append(
                f"{c} ofertas detectadas — mercado laboral con actividad"
            )
        return a

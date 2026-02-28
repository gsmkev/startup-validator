"""
SET Financial scanner — tributary statistics by sector from portal.set.gov.py.

High facturation = large market = opportunity (negative signal direction).
Portal may use JS/forms; this is best-effort. When available, provides
real market size in Gs.
"""
import logging
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from models import Competitor, ScanResult, ScannerAnalysis
from scanners.base import BaseScanner

logger = logging.getLogger("validator.scanners.set")

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36"
)
_BASE_URL = "https://portal.set.gov.py"
_STATS_URL = "https://portal.set.gov.py/estadisticas"


class SetFinancialScanner(BaseScanner):
    name = "SET PY"
    tier = "deep"
    weight = 25
    signal_direction = "negative"  # High facturation = large market = opportunity
    display_label = "Estadísticas SET"

    async def scan(self, keywords: list[str]) -> ScanResult:
        logger.info("scan keywords=%s", keywords[:2])
        try:
            resp = await self.client.get(
                _STATS_URL,
                timeout=8.0,
                headers={"User-Agent": _USER_AGENT},
                follow_redirects=True,
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            # Look for tables with economic/financial data
            tables = soup.select("table, .tabla-estadisticas, [class*='estadistica']")
            total_mention = 0
            competitors: list[Competitor] = []

            for keyword in keywords[:2]:
                kw_lower = keyword.lower()
                for table in tables:
                    text = table.get_text()
                    if kw_lower in text.lower():
                        total_mention += 1
                        # Extract rows that might contain sector data
                        rows = table.select("tr")
                        for row in rows[:3]:
                            cells = row.select("td, th")
                            if len(cells) >= 2:
                                name = cells[0].get_text(strip=True)[:80]
                                if name and kw_lower in name.lower():
                                    competitors.append(
                                        Competitor(
                                            name=name,
                                            source="SET Estadísticas",
                                            detail=cells[1].get_text(strip=True)[:100],
                                        )
                                    )

            if total_mention == 0 and not competitors:
                logger.debug("SET: no data found, portal may be JS-rendered")
                # Portal may be JS-rendered; return minimal signal
                return ScanResult(
                    source=self.name,
                    count=0,
                    competitors=[],
                    raw_signal=0.0,
                    hints=["Portal SET requiere análisis manual de estadísticas por sector"],
                )

            # Negative: more facturation = bigger market = opportunity
            raw = -min(total_mention / 5, 1.0) * 0.3
            return ScanResult(
                source=self.name,
                count=total_mention,
                competitors=competitors[:5],
                raw_signal=raw,
                hints=[f"Referencias tributarias en SET para sector"] if total_mention > 0 else [],
            )
        except Exception as e:
            logger.warning("SET scan failed: %s", e)
            return ScanResult(
                source=self.name,
                available=False,
                hints=[f"Portal SET no disponible: {str(e)[:80]}"],
            )

    @classmethod
    def analyze(cls, result: ScanResult, score: int) -> ScannerAnalysis:
        a = ScannerAnalysis()
        if not result.available:
            return a
        if result.count > 0:
            a.strengths.append(
                "Datos tributarios SET disponibles — permite estimar tamaño real de mercado"
            )
        return a

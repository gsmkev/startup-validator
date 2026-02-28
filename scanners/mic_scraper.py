import logging

from bs4 import BeautifulSoup

from models import ScanResult, ScannerAnalysis, Competitor
from scanners.base import BaseScanner

logger = logging.getLogger("validator.scanners.mic")

# emprendedores.php returns 404; convocatorias.php lists emprendimientos with h5 "Name - Sector"
CONVOCATORIAS_URL = "https://portalemprendedor.mic.gov.py/convocatorias.php"


class MicScraper(BaseScanner):
    name = "MIC"
    tier = "deep"
    weight = 20
    signal_direction = "positive"
    display_label = "Startups MIC"

    async def scan(self, keywords: list[str]) -> ScanResult:
        logger.info("scan keywords=%s", keywords[:2])
        try:
            competitors = []
            seen_names: set[str] = set()

            resp = await self.client.get(
                CONVOCATORIAS_URL,
                timeout=8.0,
                headers={"User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)"}
            )
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "lxml")
            # Emprendimientos listed as h5 with "Name - Sector" format (exclude modal titles)
            all_h5 = soup.select("h5")
            kw_lower = [k.lower() for k in keywords[:3]]

            for h5 in all_h5:
                text = h5.get_text(strip=True)
                # Skip modal/system titles
                if not text or len(text) < 4 or "modal" in str(h5.get("id", "")).lower():
                    continue
                # Match "Name - Sector" format (emprendimiento entries)
                if " - " in text and not text.startswith(("No tenes", "Acceso", "Recuperar")):
                    name_part = text.split(" - ")[0].strip()
                    sector_part = text.split(" - ")[-1].strip() if " - " in text else ""
                    if not name_part:
                        continue
                    # Filter by keyword match
                    text_lower = text.lower()
                    if any(kw in text_lower for kw in kw_lower):
                        if name_part.lower() not in seen_names:
                            seen_names.add(name_part.lower())
                            competitors.append(Competitor(
                                name=name_part,
                                ruc=None,
                                source="MIC Portal Emprendedor",
                                detail=sector_part if sector_part else None,
                            ))

            logger.info("MIC done count=%d", len(competitors))
            return ScanResult(
                source="MIC",
                count=len(competitors),
                competitors=competitors[:10],
                raw_signal=min(len(competitors) / 10, 1.0),
            )
        except Exception as e:
            logger.warning("MIC scan failed: %s", e)
            return ScanResult(source="MIC", available=False, hints=[str(e)])

    @classmethod
    def analyze(cls, result: ScanResult, score: int) -> ScannerAnalysis:
        a = ScannerAnalysis()
        if not result.available:
            return a

        if result.count == 0:
            a.strengths.append("Sin startups en el Portal Emprendedor MIC — primera mover advantage disponible")
        elif result.count <= 3:
            a.strengths.append(f"Solo {result.count} startup(s) en MIC — poca competencia en etapa temprana")
        else:
            a.weaknesses.append(f"{result.count} startups registradas en MIC ya compiten en este segmento")

        return a

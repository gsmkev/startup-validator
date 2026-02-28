from bs4 import BeautifulSoup
from models import ScanResult, Competitor
from scanners.base import BaseScanner


class MicScraper(BaseScanner):
    SEARCH_URL = "https://portalemprendedor.mic.gov.py/emprendedores.php"
    FALLBACK_URL = "https://portalemprendedor.mic.gov.py/convocatoria.php"

    async def scan(self, keywords: list[str]) -> ScanResult:
        try:
            competitors = []

            for keyword in keywords[:2]:
                try:
                    resp = await self.client.get(
                        self.SEARCH_URL,
                        params={"buscar": keyword},
                        timeout=5.0,
                        headers={"User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)"}
                    )
                    resp.raise_for_status()

                    soup = BeautifulSoup(resp.text, "lxml")
                    # Parse startup cards/listings from the page
                    cards = soup.select(".emprendedor-card, .startup-item, article, .card")

                    for card in cards[:5]:
                        name = card.select_one("h2, h3, .nombre, .title")
                        desc = card.select_one("p, .descripcion, .description")
                        competitors.append(Competitor(
                            name=name.text.strip() if name else "Emprendimiento MIC",
                            ruc=None,
                            source="MIC Portal Emprendedor",
                            detail=desc.text.strip()[:100] if desc else ""
                        ))
                except Exception:
                    # Try fallback URL
                    try:
                        resp = await self.client.get(self.FALLBACK_URL, timeout=5.0)
                        soup = BeautifulSoup(resp.text, "lxml")
                        cards = soup.select("article, .card, .item")
                        for card in cards[:3]:
                            name = card.select_one("h2, h3, .title")
                            if name and keyword.lower() in name.text.lower():
                                competitors.append(Competitor(
                                    name=name.text.strip(),
                                    ruc=None,
                                    source="MIC Portal Emprendedor",
                                    detail=""
                                ))
                    except Exception:
                        continue

            return ScanResult(
                source="MIC",
                count=len(competitors),
                competitors=competitors,
                raw_signal=min(len(competitors) / 10, 1.0) * 0.3
            )
        except Exception as e:
            return ScanResult(source="MIC", available=False, hints=[str(e)])

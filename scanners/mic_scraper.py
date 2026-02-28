from bs4 import BeautifulSoup
from models import ScanResult, ScannerAnalysis, Competitor
from scanners.base import BaseScanner


class MicScraper(BaseScanner):
    name = "MIC"
    tier = "deep"
    weight = 20
    signal_direction = "positive"
    display_label = "Startups MIC"

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
                raw_signal=min(len(competitors) / 10, 1.0)
            )
        except Exception as e:
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

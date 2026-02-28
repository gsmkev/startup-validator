import xml.etree.ElementTree as ET
from models import ScanResult, ScannerAnalysis
from scanners.base import BaseScanner


class GoogleNewsScanner(BaseScanner):
    name = "Google News PY"
    tier = "quick"
    weight = 15
    signal_direction = "positive"
    display_label = "Prensa PY"

    RSS_URL = "https://news.google.com/rss/search"

    async def scan(self, keywords: list[str]) -> ScanResult:
        try:
            query = " ".join(keywords[:2]) + " Paraguay emprendimiento startup"
            resp = await self.client.get(
                self.RSS_URL,
                params={"q": query, "hl": "es-419", "gl": "PY", "ceid": "PY:es"},
                timeout=4.0
            )
            resp.raise_for_status()

            root = ET.fromstring(resp.text)
            items = root.findall(".//item")
            recent_items = items[:20]

            news_titles = [
                item.find("title").text
                for item in recent_items
                if item.find("title") is not None
            ]

            recent_count = len(recent_items)

            hints = []
            if recent_count > 10:
                hints.append(f"{recent_count} artículos de prensa recientes sobre este sector en Paraguay")
            elif recent_count == 0:
                hints.append("Sin cobertura de prensa local — sector poco explorado públicamente")

            return ScanResult(
                source="Google News PY",
                count=recent_count,
                competitors=[],
                raw_signal=min(recent_count / 20, 1.0),
                hints=hints,
                news_samples=news_titles[:3]
            )
        except Exception as e:
            return ScanResult(source="Google News PY", available=False, hints=[str(e)])

    @classmethod
    def analyze(cls, result: ScanResult, score: int) -> ScannerAnalysis:
        a = ScannerAnalysis()
        if not result.available:
            return a

        if result.count == 0:
            a.strengths.append("Sin cobertura de prensa local — oportunidad de construir la narrativa de mercado desde cero")
        elif result.count <= 5:
            a.strengths.append("Poca cobertura mediática — sector no sobre-analizado, fácil diferenciarse")
        elif result.count <= 15:
            a.strengths.append(f"{result.count} artículos recientes — sector con interés mediático pero no saturado")
        else:
            a.weaknesses.append(f"{result.count} artículos de prensa recientes — sector muy visible, expectativas altas del mercado")

        return a

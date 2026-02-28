import xml.etree.ElementTree as ET
from models import ScanResult
from scanners.base import BaseScanner


class GoogleNewsScanner(BaseScanner):
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
            recent_items = items[:20]  # last 20 news articles

            # Extract titles for hints
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
                raw_signal=min(recent_count / 20, 1.0) * 0.15,
                hints=hints,
                news_samples=news_titles[:3]
            )
        except Exception as e:
            return ScanResult(source="Google News PY", available=False, hints=[str(e)])

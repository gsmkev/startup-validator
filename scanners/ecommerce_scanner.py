"""
E-commerce scanner — detects competitors on Paraguayan marketplaces.

Sources:
  - MercadoLibre PY: listado.mercadolibre.com.py (parse embedded JSON for count)
  - Garex: garex.com.py (scrape listing count when available)
"""
import re
import logging
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from models import Competitor, ScanResult, ScannerAnalysis
from scanners.base import BaseScanner

logger = logging.getLogger("validator.scanners.ecommerce")

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
_SOURCES = [
    ("MercadoLibre", "https://listado.mercadolibre.com.py/{keyword}"),
    ("Garex", "https://garex.com.py/search?q={keyword}"),
]


class EcommerceScanner(BaseScanner):
    name = "Ecommerce PY"
    tier = "deep"
    weight = 20
    signal_direction = "positive"
    display_label = "E-commerce PY"


    async def scan(self, keywords: list[str]) -> ScanResult:
        logger.info("scan keywords=%s", keywords[:2])
        total_listings = 0
        competitors: list[Competitor] = []
        seen: set[str] = set()

        for keyword in keywords[:2]:
            for source_name, url_tpl in _SOURCES:
                try:
                    url = url_tpl.replace("{keyword}", quote_plus(keyword))
                    resp = await self.client.get(
                        url,
                        follow_redirects=True,
                        timeout=10.0,
                        headers={"User-Agent": _USER_AGENT},
                    )
                    resp.raise_for_status()
                    text = resp.text

                    if "mercadolibre" in url.lower():
                        # Parse embedded __PRELOADED_STATE__ or similar JSON
                        match = re.search(r'"results":\s*\[(.*?)\](?=\s*,\s*")', text, re.DOTALL)
                        if match:
                            inner = match.group(1)
                            item_ids = re.findall(r'"([A-Z]{3}\d+)"', inner)
                            count = len(item_ids)
                            total_listings += count
                            for iid in item_ids[:5]:
                                if iid not in seen:
                                    seen.add(iid)
                                    competitors.append(
                                        Competitor(
                                            name=f"Vendedor ML #{iid[-6:]}",
                                            source=f"Ecommerce/{source_name}",
                                            detail=keyword,
                                            url=f"https://articulo.mercadolibre.com.py/{iid}",
                                        )
                                    )
                        else:
                            # Fallback: count MPY item IDs in page
                            ids = re.findall(r'MPY\d{9,}', text)
                            total_listings += len(set(ids))

                    elif "garex" in url.lower():
                        soup = BeautifulSoup(text, "lxml")
                        # Common listing selectors
                        items = soup.select(
                            ".product-card, .product-item, .listing-item, "
                            "[data-product], .item, article"
                        )
                        if items:
                            total_listings += len(items)
                            for item in items[:5]:
                                name_el = item.select_one(
                                    "h2, h3, .title, .product-name, [class*='name']"
                                )
                                name = name_el.get_text(strip=True)[:80] if name_el else f"Garex #{len(competitors)+1}"
                                if name and name.lower() not in seen:
                                    seen.add(name.lower())
                                    competitors.append(
                                        Competitor(
                                            name=name,
                                            source=f"Ecommerce/{source_name}",
                                            detail=keyword,
                                        )
                                    )

                except Exception as e:
                    logger.debug("Ecommerce %s %r failed: %s", source_name, keyword, e)
                    continue

        count = total_listings if total_listings > len(competitors) else len(competitors)
        logger.info("Ecommerce done count=%d competitors=%d", count, len(competitors))
        return ScanResult(
            source=self.name,
            count=count,
            competitors=competitors[:10],
            raw_signal=min(count / 30, 1.0),
            hints=[f"{count} listados en marketplaces PY"] if count > 0 else [],
        )

    @classmethod
    def analyze(cls, result: ScanResult, score: int) -> ScannerAnalysis:
        a = ScannerAnalysis()
        if not result.available:
            return a
        c = result.count
        if c == 0:
            a.strengths.append(
                "Sin competidores detectados en MercadoLibre/Garex — oportunidad en canal digital"
            )
        elif c <= 10:
            a.strengths.append(
                f"Solo {c} listados en e-commerce paraguayo — baja saturación en marketplaces"
            )
        else:
            a.weaknesses.append(
                f"{c} listados en marketplaces — sector activo en venta digital"
            )
        return a

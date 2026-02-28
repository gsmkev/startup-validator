import asyncio
from models import ScanResult, Competitor
from scanners.base import BaseScanner


class TurucScanner(BaseScanner):
    BASE_URL = "https://turuc.com.py/api"

    async def scan(self, keywords: list[str]) -> ScanResult:
        try:
            results = []
            total_count = 0
            active_count = 0

            # Use only the primary keyword (first one = product/service type).
            # Using the second keyword risks inflating the count with CLIENT types
            # e.g. "cooperativas" (2753 hits) are customers, not competitors.
            for keyword in keywords[:1]:
                try:
                    resp = await self.client.get(
                        f"{self.BASE_URL}/contribuyente/table",
                        # length=10 required — length=50 returns 400 for accented keywords
                        params={"draw": 1, "start": 0, "length": 10, "search": keyword},
                        timeout=5.0
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    total_count += data.get("recordsTotal", 0)

                    for item in data.get("data", [])[:5]:
                        estado = item.get("estado", "")
                        if estado == "ACTIVO":
                            active_count += 1
                        results.append(Competitor(
                            name=item.get("razonSocial", ""),
                            ruc=item.get("ruc", ""),
                            source="DNIT/TuRuc",
                            detail=f"Estado: {estado}" if estado else None
                        ))
                except Exception:
                    continue

            hints = []
            if total_count > 0 and active_count == 0:
                hints.append(f"{total_count} empresas en DNIT (incluye canceladas y suspendidas)")

            # Threshold 80: ~80 empresas en el sector = mercado con competencia real
            return ScanResult(
                source="TuRuc",
                count=total_count,
                competitors=results[:5],
                raw_signal=min(total_count / 80, 1.0),
                hints=hints
            )
        except Exception as e:
            return ScanResult(source="TuRuc", available=False, hints=[str(e)])

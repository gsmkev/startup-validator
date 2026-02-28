import os
from models import ScanResult
from scanners.base import BaseScanner

# V3 API — basePath from swagger spec at /datos/api/v3/doc/swagger.json
_V3_BASE = "https://www.contrataciones.gov.py/datos/api/v3/doc"


class DncpScanner(BaseScanner):
    _cached_token: str | None = None

    async def get_access_token(self) -> str:
        if DncpScanner._cached_token:
            return DncpScanner._cached_token

        request_token = os.getenv("DNCP_REQUEST_TOKEN", "")
        # V3 auth: POST with JSON body {"request_token": ...}, returns a proper JWT
        resp = await self.client.post(
            f"{_V3_BASE}/oauth/token",
            json={"request_token": request_token},
            timeout=6.0
        )
        resp.raise_for_status()
        token = resp.json()["access_token"]
        DncpScanner._cached_token = token
        return token

    async def scan(self, keywords: list[str]) -> ScanResult:
        if not os.getenv("DNCP_REQUEST_TOKEN"):
            return ScanResult(
                source="DNCP",
                available=False,
                hints=["Configurar DNCP_REQUEST_TOKEN para habilitar"]
            )

        try:
            token = await self.get_access_token()
            total_demand = 0

            for keyword in keywords[:2]:
                try:
                    resp = await self.client.get(
                        f"{_V3_BASE}/search/processes",
                        # v3 uses tender.title instead of q
                        params={"tender.title": keyword, "items_per_page": 5},
                        headers={"Authorization": token},
                        timeout=5.0
                    )
                    resp.raise_for_status()
                    total_demand += resp.json().get("pagination", {}).get("total_items", 0)
                except Exception:
                    continue

            return ScanResult(
                source="DNCP",
                count=total_demand,
                competitors=[],  # state is not a competitor, it's a customer
                raw_signal=-min(total_demand / 100, 1.0) * 0.3,  # NEGATIVE: opportunity
                hints=[f"El Estado paraguayo tiene {total_demand} licitaciones en este sector"]
            )
        except Exception as e:
            return ScanResult(source="DNCP", available=False, hints=[str(e)])

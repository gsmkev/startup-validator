import logging
import os
import time

from models import ScanResult, ScannerAnalysis
from scanners.base import BaseScanner

logger = logging.getLogger("validator.scanners.dncp")

_V3_BASE = "https://www.contrataciones.gov.py/datos/api/v3/doc"
_TOKEN_TTL_SECONDS = 3000


class DncpScanner(BaseScanner):
    name = "DNCP"
    tier = "deep"
    weight = 20
    signal_direction = "negative"
    requires_env = ["DNCP_REQUEST_TOKEN"]
    display_label = "Licitaciones DNCP"

    _cached_token: tuple[str, float] | None = None

    async def get_access_token(self) -> str:
        if DncpScanner._cached_token:
            token, expires_at = DncpScanner._cached_token
            if time.monotonic() < expires_at:
                return token

        request_token = os.getenv("DNCP_REQUEST_TOKEN", "")
        resp = await self.client.post(
            f"{_V3_BASE}/oauth/token",
            json={"request_token": request_token},
            timeout=6.0
        )
        resp.raise_for_status()
        token = resp.json()["access_token"]
        DncpScanner._cached_token = (token, time.monotonic() + _TOKEN_TTL_SECONDS)
        return token

    async def scan(self, keywords: list[str]) -> ScanResult:
        logger.info("scan keywords=%s", keywords[:2])
        if not os.getenv("DNCP_REQUEST_TOKEN"):
            logger.warning("DNCP: DNCP_REQUEST_TOKEN not set")
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
                        params={"tender.title": keyword, "items_per_page": 5},
                        headers={"Authorization": token},
                        timeout=5.0
                    )
                    resp.raise_for_status()
                    total_demand += resp.json().get("pagination", {}).get("total_items", 0)
                except Exception as e:
                    logger.warning("DNCP keyword %r failed: %s", keyword, e)
                    continue

            logger.info("DNCP done total_demand=%d", total_demand)
            return ScanResult(
                source="DNCP",
                count=total_demand,
                competitors=[],
                raw_signal=-min(total_demand / 100, 1.0) * 0.3,
                hints=[f"El Estado paraguayo tiene {total_demand} licitaciones en este sector"]
            )
        except Exception as e:
            logger.warning("DNCP scan failed: %s", e)
            return ScanResult(source="DNCP", available=False, hints=[str(e)])

    @classmethod
    def analyze(cls, result: ScanResult, score: int) -> ScannerAnalysis:
        a = ScannerAnalysis()
        if not result.available:
            return a

        if result.count > 50:
            a.strengths.append(f"El Estado tiene {result.count} contratos DNCP en este sector — demanda pública masiva confirmada")
        elif result.count > 10:
            a.strengths.append(f"Demanda estatal detectada ({result.count} contratos DNCP) — el Estado es un cliente potencial")
        elif result.count > 0:
            a.strengths.append(f"{result.count} contratos DNCP — sector en radar del gobierno paraguayo")

        return a

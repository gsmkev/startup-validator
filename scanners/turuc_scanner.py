import logging

from models import ScanResult, ScannerAnalysis, Competitor
from scanners.base import BaseScanner

logger = logging.getLogger("validator.scanners.turuc")


class TurucScanner(BaseScanner):
    name = "TuRuc"
    tier = "quick"
    weight = 65
    signal_direction = "positive"
    display_label = "Empresas DNIT"

    BASE_URL = "https://turuc.com.py/api"

    async def scan(self, keywords: list[str]) -> ScanResult:
        logger.info("scan keywords=%s", keywords[:2])
        try:
            results = []
            total_count = 0
            active_count = 0

            for keyword in keywords[:1]:
                try:
                    resp = await self.client.get(
                        f"{self.BASE_URL}/contribuyente/table",
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
                except Exception as e:
                    logger.warning("TuRuc keyword %r failed: %s", keyword, e)
                    continue

            logger.info("TuRuc done count=%d competitors=%d", total_count, len(results))
            hints = []
            if total_count > 0 and active_count == 0:
                hints.append(f"{total_count} empresas en DNIT (incluye canceladas y suspendidas)")

            return ScanResult(
                source="TuRuc",
                count=total_count,
                competitors=results[:5],
                raw_signal=min(total_count / 80, 1.0),
                hints=hints
            )
        except Exception as e:
            logger.warning("TuRuc scan failed: %s", e)
            return ScanResult(source="TuRuc", available=False, hints=[str(e)])

    @classmethod
    def analyze(cls, result: ScanResult, score: int) -> ScannerAnalysis:
        a = ScannerAnalysis()
        if not result.available:
            a.weaknesses.append("No se pudo consultar DNIT/TuRuc — datos de competencia incompletos")
            return a

        if result.count == 0:
            a.strengths.append("Ninguna empresa registrada en el DNIT para este sector — mercado virgen")
        elif result.count < 30:
            a.strengths.append(f"Solo {result.count} negocios en DNIT — mercado poco explotado localmente")
        elif result.count < 80:
            a.strengths.append(f"{result.count} empresas en DNIT — sector existente con espacio para nuevos jugadores")
        else:
            a.weaknesses.append(f"{result.count} empresas ya registradas en DNIT — alta competencia establecida")

        return a

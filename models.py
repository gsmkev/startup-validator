from pydantic import BaseModel
from typing import Optional


class Competitor(BaseModel):
    name: str
    ruc: Optional[str] = None
    source: str  # "DNIT/TuRuc" | "MIC" | "DNCP" | "Google News PY"
    detail: Optional[str] = None


class MarketHint(BaseModel):
    hint: str
    type: str  # "opportunity" | "warning" | "info"
    source: str


class ScanResult(BaseModel):
    source: str
    available: bool = True
    count: int = 0
    competitors: list[Competitor] = []
    raw_signal: float = 0.0    # normalized -1.0 to 1.0 (negative = opportunity)
    hints: list[str] = []
    news_samples: list[str] = []


class IdeaValidationResult(BaseModel):
    idea: str
    keywords_extracted: list[str]
    market_signal: int               # 0-100
    signal_label: str                # "mercado saturado" | "oportunidad con diferenciación" | "espacio abierto"
    recommendation: str              # in Spanish
    competitors: list[Competitor]
    market_hints: list[MarketHint]
    strengths: list[str]             # puntos fuertes del mercado para esta idea
    weaknesses: list[str]            # puntos débiles / riesgos detectados
    action_items: list[str]          # próximos pasos concretos
    pivot_suggestions: list[str]     # pivots sugeridos si el mercado está saturado
    news_samples: list[str]          # titulares de prensa recientes
    sources_queried: list[str]
    sources_unavailable: list[str]
    scan_duration_ms: int
    raw_scores: dict                 # debug: {"turuc": 0.7, "dncp": -0.2, ...}

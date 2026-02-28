from pydantic import BaseModel
from typing import Optional
from dataclasses import dataclass, field


class Competitor(BaseModel):
    name: str
    ruc: Optional[str] = None
    source: str  # "DNIT/TuRuc" | "MIC" | "DNCP" | "Google News PY" | "Web/*"
    detail: Optional[str] = None
    url: Optional[str] = None


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


@dataclass
class ScannerAnalysis:
    """Per-scanner analysis output returned by BaseScanner.analyze()."""
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    pivot_suggestions: list[str] = field(default_factory=list)


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
    # AI-enhanced analysis via OpenRouter (empty if OPENROUTER_API_KEY not set)
    ai_recommendation: str = ""
    quick_wins: list[str] = []       # 3 concrete 90-day actions
    red_flags: list[str] = []        # Paraguay-specific risks
    source_counts: dict[str, int]    # per-source hit counts: {"TuRuc": 42, "MIC": 3, ...}
    sources_queried: list[str]
    sources_unavailable: list[str]
    scan_duration_ms: int
    raw_scores: dict                 # debug: {"turuc": 0.7, "dncp": -0.2, ...}

Ahora tengo todo lo necesario — incluyendo un detalle crítico: la DNCP API v2 **requiere OAuth** (registro + credenciales). Ajusto el prompt con fuentes 100% reales y sus constraints exactos. [contrataciones.gov](https://www.contrataciones.gov.py/datos/api/v2/)

***

```
You are a senior full-stack engineer. Build "paraguay-idea-mcp" — a Python 
MCP server that validates startup ideas against LIVE Paraguayan web sources.
No CSV files. All data must come from real HTTP requests at runtime.
This is a 5-hour hackathon project. Prioritize working code over perfection.

## Core Concept
When an AI agent is about to suggest or build something, it first calls
`validate_idea("mi idea")` and gets back a `market_signal` score (0-100)
based on real, live data from Paraguayan government and market APIs.
Higher score = more saturated market = harder to differentiate.

## Tech Stack
- Python 3.11+
- fastmcp >= 2.0 (MCP server, stdio transport)
- httpx >= 0.27 (async HTTP, all requests)
- beautifulsoup4 + lxml (HTML scraping fallback)
- pydantic v2 (response models)
- python-dotenv
- uvicorn + fastapi (REST bridge for frontend on port 8001)
- Next.js 15 + TypeScript + Tailwind CSS + shadcn/ui (frontend)

## Project File Structure
```
paraguay-idea-mcp/
├── pyproject.toml
├── .env.example
├── README.md
├── server.py              # FastMCP entry point, stdio transport
├── rest_bridge.py         # FastAPI app on :8001, wraps MCP tools for frontend
├── tools.py               # @mcp.tool() definitions
├── scorer.py              # market_signal formula
├── models.py              # Pydantic models
├── scanners/
│   ├── __init__.py
│   ├── base.py            # Abstract BaseScanner + shared httpx client
│   ├── turuc_scanner.py   # TuRuc public API (NO auth required)
│   ├── dncp_scanner.py    # DNCP open contracting API (OAuth2 required)
│   ├── mic_scraper.py     # MIC Portal Emprendedor HTML scraper
│   └── google_news_scanner.py  # Google News RSS for Paraguayan press coverage
└── keyword_extractor.py   # Spanish keyword extraction, no external NLP libs

frontend/
├── app/
│   ├── page.tsx
│   └── api/validate/route.ts   # proxy to rest_bridge :8001
├── components/
│   ├── IdeaValidatorPanel.tsx
│   ├── SignalGauge.tsx
│   ├── CompetitorCard.tsx
│   └── MetricCard.tsx
└── lib/api.ts
```

---

## SCANNER 1 — TuRuc API (PRIMARY, no auth)

**Docs**: https://docs.turuc.com.py/docs/api/introduccion-api  
**Base URL**: https://turuc.com.py/api  
**Auth**: None required — fully public API

### Endpoints to use:

#### Search contributors (main endpoint):
```
GET https://turuc.com.py/api/contribuyente/table
  ?draw=1
  &start=0
  &length=50
  &search={keyword}
```
Returns DataTables-format JSON with `recordsTotal` (total matching contributors)
and `data` array with contributor objects.

#### Single contributor lookup (for detail):
```
GET https://turuc.com.py/api/contribuyente/{ruc}
```

### Implementation:
```python
class TurucScanner(BaseScanner):
    BASE_URL = "https://turuc.com.py/api"

    async def scan(self, keywords: list[str]) -> ScanResult:
        results = []
        total_count = 0
        
        for keyword in keywords[:2]:  # max 2 keywords to avoid rate limits
            resp = await self.client.get(
                f"{self.BASE_URL}/contribuyente/table",
                params={"draw": 1, "start": 0, "length": 50, "search": keyword},
                timeout=4.0
            )
            data = resp.json()
            total_count += data.get("recordsTotal", 0)
            
            for item in data.get("data", [])[:5]:
                results.append(Competitor(
                    name=item.get("dNombreRazonSocial", ""),
                    ruc=item.get("dRuc", ""),
                    source="DNIT/TuRuc",
                    detail=item.get("dActividadEconomica", "")
                ))
        
        return ScanResult(
            source="TuRuc",
            count=total_count,
            competitors=results[:5],
            raw_signal=min(total_count / 300, 1.0)  # normalized 0.0-1.0
        )
```

**Saturation logic**: `recordsTotal` tells you how many active businesses 
exist in that sector. >300 = saturated, <50 = open space.

---

## SCANNER 2 — DNCP Open Contracting (OAuth2 required)

**Base URL**: https://www.contrataciones.gov.py/datos/api/v2/  
**Auth**: OAuth2 — needs registration at contrataciones.gov.py/datos  
**Limit**: 5000 requests per 15 minutes

### Auth flow:
```python
# .env vars needed:
# DNCP_REQUEST_TOKEN=<base64 of customer_key:customer_secret>

async def get_access_token(self) -> str:
    resp = await self.client.post(
        "https://www.contrataciones.gov.py/datos/api/v2/oauth/token",
        headers={"Authorization": f"Basic {os.getenv('DNCP_REQUEST_TOKEN')}"},
        timeout=5.0
    )
    return resp.json()["access_token"]
```

### Endpoints to use:
```
GET /datos/api/v2/search/processes?q={keyword}&pageSize=10
Authorization: Bearer {access_token}
```
Returns procurement processes. `pagination.totalItems` = demand signal.

```
GET /datos/api/v2/search/products?q={keyword}&pageSize=10  
```
Returns products/services the state has purchased.

### Implementation notes:
- Cache the access_token in memory (valid for 1 hour typically)
- If DNCP_REQUEST_TOKEN not set in .env, skip this scanner gracefully
  and mark source as "no configurado" in sources_queried
- High `totalItems` = state actively buys in this sector = OPPORTUNITY
  (this REDUCES market_signal, it's a positive validation signal)

```python
class DncpScanner(BaseScanner):
    async def scan(self, keywords: list[str]) -> ScanResult:
        if not os.getenv("DNCP_REQUEST_TOKEN"):
            return ScanResult(source="DNCP", available=False, 
                              hint="Configurar DNCP_REQUEST_TOKEN para habilitar")
        
        token = await self.get_access_token()
        total_demand = 0
        
        for keyword in keywords[:2]:
            resp = await self.client.get(
                "https://www.contrataciones.gov.py/datos/api/v2/search/processes",
                params={"q": keyword, "pageSize": 10},
                headers={"Authorization": f"Bearer {token}"},
                timeout=4.0
            )
            total_demand += resp.json().get("pagination", {}).get("totalItems", 0)
        
        return ScanResult(
            source="DNCP",
            count=total_demand,
            competitors=[],  # state is not a competitor, it's a customer
            raw_signal=-min(total_demand / 100, 1.0) * 0.3,  # NEGATIVE: opportunity
            hints=[f"El Estado paraguayo tiene {total_demand} procesos de compra en este sector"]
        )
```

---

## SCANNER 3 — MIC Portal Emprendedor (HTML scraper)

**URL**: https://portalemprendedor.mic.gov.py  
**Auth**: None  
**Method**: HTTP GET + BeautifulSoup HTML parsing

The portal lists registered startups and entrepreneurship programs.
Scrape the startup registry and convocatorias pages.

```python
class MicScraper(BaseScanner):
    SEARCH_URL = "https://portalemprendedor.mic.gov.py/emprendedores.php"
    
    async def scan(self, keywords: list[str]) -> ScanResult:
        competitors = []
        
        for keyword in keywords[:2]:
            resp = await self.client.get(
                self.SEARCH_URL,
                params={"buscar": keyword},
                timeout=5.0,
                headers={"User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)"}
            )
            
            soup = BeautifulSoup(resp.text, "lxml")
            # Parse startup cards/listings from the page
            # Adapt selectors to actual DOM structure found
            cards = soup.select(".emprendedor-card, .startup-item, article")
            
            for card in cards[:5]:
                name = card.select_one("h2, h3, .nombre")
                desc = card.select_one("p, .descripcion")
                competitors.append(Competitor(
                    name=name.text.strip() if name else "Emprendimiento MIC",
                    ruc=None,
                    source="MIC Portal Emprendedor",
                    detail=desc.text.strip()[:100] if desc else ""
                ))
        
        return ScanResult(
            source="MIC",
            count=len(competitors),
            competitors=competitors,
            raw_signal=min(len(competitors) / 10, 1.0) * 0.3
        )
    
    # IMPORTANT: If the portal changes its HTML structure,
    # fall back to scraping https://portalemprendedor.mic.gov.py/convocatoria.php
    # and https://www.mipymes.gov.py/dinaem/ for program listings
```

---

## SCANNER 4 — Google News RSS (PRESS COVERAGE SIGNAL)

**URL**: `https://news.google.com/rss/search?q={keyword}+Paraguay&hl=es-419&gl=PY&ceid=PY:es`  
**Auth**: None  
**Method**: RSS XML parsing with httpx + xml.etree.ElementTree

This measures PRESS COVERAGE = how much media attention a sector already has.
High coverage = market is known/validated but may be crowded.
Very low coverage = either too early or not viable.

```python
class GoogleNewsScanner(BaseScanner):
    RSS_URL = "https://news.google.com/rss/search"
    
    async def scan(self, keywords: list[str]) -> ScanResult:
        import xml.etree.ElementTree as ET
        
        query = " ".join(keywords[:2]) + " Paraguay emprendimiento startup"
        resp = await self.client.get(
            self.RSS_URL,
            params={"q": query, "hl": "es-419", "gl": "PY", "ceid": "PY:es"},
            timeout=4.0
        )
        
        root = ET.fromstring(resp.text)
        items = root.findall(".//item")
        recent_items = items[:20]  # last 20 news articles
        
        # Extract titles and sources for hints
        news_titles = [item.find("title").text for item in recent_items if item.find("title") is not None]
        
        # Count articles from last 30 days (check pubDate)
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
            news_samples=news_titles[:3]  # for display in UI
        )
```

---

## Models (models.py)

```python
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
    sources_queried: list[str]
    sources_unavailable: list[str]
    scan_duration_ms: int
    raw_scores: dict                 # debug: {"turuc": 0.7, "dncp": -0.2, ...}
```

---

## Scoring Formula (scorer.py)

```python
import time

def calculate_market_signal(scan_results: list[ScanResult]) -> tuple[int, str, str]:
    """
    Returns (score: int 0-100, label: str, recommendation: str)
    
    Weights:
    - TuRuc (business density): 50% weight — primary saturation signal
    - MIC (local startup competition): 30% weight — direct competition
    - Google News (press coverage): 15% weight — market awareness
    - DNCP (state demand): -20% discount — opportunity/validation signal
    """
    scores_by_source = {r.source: r.raw_signal for r in scan_results if r.available}
    
    turuc_signal   = scores_by_source.get("TuRuc", 0.0)   * 50
    mic_signal     = scores_by_source.get("MIC", 0.0)      * 30
    news_signal    = scores_by_source.get("Google News PY", 0.0) * 15
    dncp_discount  = scores_by_source.get("DNCP", 0.0)     * 20  # already negative
    
    raw = turuc_signal + mic_signal + news_signal + dncp_discount
    score = max(0, min(100, int(raw)))
    
    if score > 70:
        label = "mercado saturado"
        rec = (
            "Este sector tiene alta densidad de empresas registradas en Paraguay. "
            "Considerá diferenciarte por departamento (interior vs Asunción), "
            "segmento (cooperativas, pymes agro, microempresas) o modelo de precios."
        )
    elif score > 30:
        label = "oportunidad con diferenciación"
        rec = (
            "Existe mercado pero hay espacio para un jugador enfocado. "
            "Identificá el nicho específico paraguayo que los actores actuales no cubren bien."
        )
    else:
        label = "espacio abierto"
        rec = (
            "Muy poca competencia local registrada. "
            "El mercado paraguayo tiene espacio real para este producto. "
            "Procedé a construir con foco en tracción temprana."
        )
    
    return score, label, rec
```

---

## Keyword Extractor (keyword_extractor.py)

```python
import re

STOPWORDS_ES = {
    "quiero", "hacer", "una", "un", "para", "que", "con", "los", "las",
    "app", "aplicacion", "aplicación", "sistema", "plataforma", "herramienta",
    "servicio", "producto", "web", "online", "digital", "nuevo", "nueva",
    "del", "de", "en", "el", "la", "por", "como", "donde", "hay", "ver",
    "usar", "crear", "construir", "desarrollar", "idea", "proyecto", "startup"
}

# Maps Spanish terms to Paraguayan economic sector keywords for better API queries
SECTOR_MAP = {
    "pago": "fintech pagos",
    "fintech": "servicios financieros",
    "cooperativa": "cooperativa ahorro crédito",
    "campo": "agricultura agropecuario",
    "ganado": "ganadería agropecuario",
    "soja": "agricultura exportación",
    "delivery": "logística entregas",
    "comida": "gastronomía alimentación",
    "salud": "salud medicina",
    "educacion": "educación enseñanza",
    "transporte": "transporte logística",
    "turismo": "turismo hotelería",
    "construccion": "construcción inmobiliario",
    "retail": "comercio minorista",
    "rrhh": "recursos humanos",
    "contabilidad": "servicios contables",
}

def extract_keywords(idea: str) -> list[str]:
    idea_lower = idea.lower()
    # Remove accents for matching
    normalized = idea_lower.translate(str.maketrans("áéíóúü", "aeiouu"))
    
    tokens = re.findall(r'\b[a-záéíóúü]{4,}\b', normalized)
    filtered = [t for t in tokens if t not in STOPWORDS_ES]
    
    # Expand with sector map
    expanded = []
    for token in filtered:
        if token in SECTOR_MAP:
            expanded.extend(SECTOR_MAP[token].split())
        else:
            expanded.append(token)
    
    # Deduplicate preserving order, return top 4
    seen = set()
    result = []
    for kw in expanded:
        if kw not in seen:
            seen.add(kw)
            result.append(kw)
    
    return result[:4]
```

---

## MCP Tool (tools.py)

```python
import asyncio, time
from fastmcp import FastMCP
from scanners.turuc_scanner import TurucScanner
from scanners.dncp_scanner import DncpScanner
from scanners.mic_scraper import MicScraper
from scanners.google_news_scanner import GoogleNewsScanner
from keyword_extractor import extract_keywords
from scorer import calculate_market_signal
from models import IdeaValidationResult, MarketHint

mcp = FastMCP("paraguay-idea-mcp")

SCANNERS_QUICK = [TurucScanner, GoogleNewsScanner]
SCANNERS_DEEP  = [TurucScanner, DncpScanner, MicScraper, GoogleNewsScanner]

@mcp.tool()
async def validate_idea(
    idea: str,
    depth: str = "quick"
) -> dict:
    """
    Validates a startup idea against real Paraguayan market data.
    Returns market_signal (0-100), competitors, and actionable hints.
    ALWAYS call this before suggesting or building any new product or startup.
    
    Args:
        idea: Description of the startup idea in Spanish
        depth: "quick" (TuRuc + Google News, ~2s) or 
               "deep" (all 4 sources in parallel, ~5s)
    """
    start = time.monotonic()
    keywords = extract_keywords(idea)
    
    scanner_classes = SCANNERS_DEEP if depth == "deep" else SCANNERS_QUICK
    scanners = [cls() for cls in scanner_classes]
    
    # Run all scanners in parallel
    scan_results = await asyncio.gather(
        *[s.scan(keywords) for s in scanners],
        return_exceptions=True
    )
    
    # Filter out exceptions (failed scanners), log them
    valid_results = []
    failed_sources = []
    for r in scan_results:
        if isinstance(r, Exception):
            failed_sources.append(str(r))
        else:
            valid_results.append(r)
    
    score, label, recommendation = calculate_market_signal(valid_results)
    
    # Aggregate competitors and hints
    all_competitors = []
    all_hints = []
    for r in valid_results:
        all_competitors.extend(r.competitors)
        for h in r.hints:
            all_hints.append(MarketHint(hint=h, type="info", source=r.source))
    
    # Add actionable Paraguay-specific hints based on score
    if score > 70:
        all_hints.append(MarketHint(
            hint="Pivot sugerido: enfocate en departamentos del interior (Alto Paraná, Itapúa, Concepción) donde la competencia es menor",
            type="opportunity", source="Análisis local"
        ))
    
    elapsed_ms = int((time.monotonic() - start) * 1000)
    
    result = IdeaValidationResult(
        idea=idea,
        keywords_extracted=keywords,
        market_signal=score,
        signal_label=label,
        recommendation=recommendation,
        competitors=all_competitors[:5],
        market_hints=all_hints,
        sources_queried=[r.source for r in valid_results if r.available],
        sources_unavailable=[r.source for r in valid_results if not r.available] + failed_sources,
        scan_duration_ms=elapsed_ms,
        raw_scores={r.source: round(r.raw_signal, 3) for r in valid_results}
    )
    
    return result.model_dump()
```

---

## REST Bridge (rest_bridge.py)

```python
"""
FastAPI server on port 8001.
Allows the Next.js frontend to call validate_idea without MCP protocol.
Run with: uvicorn rest_bridge:app --port 8001 --reload
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
from tools import validate_idea

app = FastAPI(title="Paraguay Idea Validator REST Bridge")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class ValidateRequest(BaseModel):
    idea: str
    depth: str = "quick"

@app.post("/validate")
async def validate(req: ValidateRequest):
    return await validate_idea(req.idea, req.depth)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "paraguay-idea-mcp"}
```

---

## server.py (MCP Entry Point)

```python
from tools import mcp

def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
```

---

## pyproject.toml

```toml
[project]
name = "paraguay-idea-mcp"
version = "0.1.0"
description = "MCP server for validating startup ideas against Paraguayan market data"
requires-python = ">=3.11"
dependencies = [
    "fastmcp>=2.0.0",
    "httpx>=0.27.0",
    "beautifulsoup4>=4.12.0",
    "lxml>=5.0.0",
    "pydantic>=2.0.0",
    "python-dotenv>=1.0.0",
    "fastapi>=0.111.0",
    "uvicorn>=0.30.0",
]

[project.scripts]
paraguay-idea-mcp = "server:main"
paraguay-idea-rest = "rest_bridge:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

---

## .env.example

```env
# Optional: Register at https://www.contrataciones.gov.py/datos/
# to get customer_key and customer_secret, then base64 encode "key:secret"
DNCP_REQUEST_TOKEN=

# Set to "true" during demo if APIs are down
MOCK_MODE=false
```

---

## OpenClaw Agent Instructions (agent.instructions.md)

```markdown
# Paraguay Startup Validator — Instrucciones del Agente

Antes de sugerir, diseñar o construir cualquier startup, producto, 
feature o herramienta, SIEMPRE ejecutá `validate_idea` primero.

## Reglas de decisión

**market_signal > 70 — mercado saturado:**
DETENTE. No escribas código ni hagas diseño.
- Reportá el número de empresas encontradas en DNIT/TuRuc
- Listá los top 3 competidores con su RUC y sector
- Sugerí 2 pivot específicos al contexto paraguayo:
  por departamento, por segmento (cooperativas/agro/pymes) o por precio
- Preguntá: "¿Querés proceder con un ángulo diferenciado, pivotar, o abandonar?"

**market_signal 30–70 — oportunidad con diferenciación:**
- Mostrá los resultados completos
- Si hay demanda DNCP, destacala como validación: "el Estado ya compra esto"
- Sugerí el nicho específico paraguayo no cubierto por los actuales jugadores
- Podés proceder si el usuario confirma el ángulo diferenciado

**market_signal < 30 — espacio abierto:**
- Informá que no hay competidores locales registrados
- Procedé a construir directamente
- Incluí el disclaimer: "validado contra datos DNIT y prensa paraguaya"

## Formato obligatorio de respuesta
1. `market_signal`: X/100 (label en español)
2. Fuentes consultadas: [lista]
3. Competidores locales: N empresas DNIT, M en MIC
4. Cobertura de prensa: N artículos recientes
5. Demanda estatal (si disponible): N contratos DNCP
6. Recomendación: [párrafo en español]
7. Hints de mercado: [lista de oportunidades o advertencias]
```

---

## Frontend — IdeaValidatorPanel.tsx

```tsx
"use client"
import { useState } from "react"
import { SignalGauge } from "./SignalGauge"
import { CompetitorCard } from "./CompetitorCard"
import { MetricCard } from "./MetricCard"

export function IdeaValidatorPanel() {
  const [idea, setIdea] = useState("")
  const [depth, setDepth] = useState<"quick" | "deep">("quick")
  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  async function handleValidate() {
    setLoading(true)
    setError("")
    try {
      const res = await fetch("/api/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ idea, depth })
      })
      setResult(await res.json())
    } catch (e) {
      setError("Error al conectar con el servidor")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6">
      <div className="space-y-3">
        <textarea
          className="w-full border rounded-xl p-4 text-base resize-none h-28 focus:ring-2 focus:ring-blue-500"
          placeholder="Describí tu idea de startup en Paraguay... ej: 'App de pagos para cooperativas del interior'"
          value={idea}
          onChange={e => setIdea(e.target.value)}
        />
        <div className="flex gap-3 items-center">
          <select
            className="border rounded-lg px-3 py-2 text-sm"
            value={depth}
            onChange={e => setDepth(e.target.value as "quick" | "deep")}
          >
            <option value="quick">Quick (2 fuentes, ~2s)</option>
            <option value="deep">Deep (4 fuentes, ~5s)</option>
          </select>
          <button
            onClick={handleValidate}
            disabled={loading || !idea.trim()}
            className="flex-1 bg-blue-700 text-white rounded-xl px-6 py-2 font-semibold
                       disabled:opacity-50 hover:bg-blue-800 transition"
          >
            {loading ? "Validando..." : "Validar Idea →"}
          </button>
        </div>
      </div>

      {error && <p className="text-red-600 text-sm">{error}</p>}

      {result && (
        <div className="space-y-4 animate-in fade-in duration-300">
          {/* Main signal */}
          <SignalGauge score={result.market_signal} label={result.signal_label} />
          
          {/* Keywords extracted */}
          <p className="text-sm text-gray-500">
            Keywords detectados: {result.keywords_extracted.join(", ")}
          </p>

          {/* Metrics row */}
          <div className="grid grid-cols-3 gap-3">
            <MetricCard
              label="Empresas DNIT"
              value={result.competitors.filter((c:any) => c.source === "DNIT/TuRuc").length}
              source="TuRuc"
            />
            <MetricCard
              label="Artículos de prensa"
              value={result.raw_scores?.["Google News PY"] 
                ? Math.round(result.raw_scores["Google News PY"] / 0.15 * 20)
                : 0}
              source="Google News PY"
            />
            <MetricCard
              label="Fuentes activas"
              value={result.sources_queried.length}
              source="Sistema"
            />
          </div>

          {/* Recommendation */}
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
            <p className="font-semibold text-blue-900 mb-1">Recomendación</p>
            <p className="text-blue-800 text-sm">{result.recommendation}</p>
          </div>

          {/* Competitors */}
          {result.competitors.length > 0 && (
            <div>
              <h3 className="font-semibold mb-2">Competidores locales encontrados</h3>
              <div className="space-y-2">
                {result.competitors.map((c: any, i: number) => (
                  <CompetitorCard key={i} competitor={c} />
                ))}
              </div>
            </div>
          )}

          {/* Market hints */}
          {result.market_hints.length > 0 && (
            <div>
              <h3 className="font-semibold mb-2">Señales de mercado</h3>
              <div className="flex flex-wrap gap-2">
                {result.market_hints.map((h: any, i: number) => (
                  <span key={i} className={`px-3 py-1 rounded-full text-xs font-medium
                    ${h.type === "opportunity" ? "bg-green-100 text-green-800" :
                      h.type === "warning" ? "bg-red-100 text-red-800" :
                      "bg-gray-100 text-gray-700"}`}>
                    {h.hint}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
```

---

## SignalGauge.tsx (SVG radial, no dependencies)

```tsx
export function SignalGauge({ score, label }: { score: number; label: string }) {
  // Paraguay flag colors for zones
  const color = score > 70 ? "#6b7280"   // gray — saturated
               : score > 30 ? "#D52B1E"  // red — opportunity
               : "#0038A8"               // blue — open space

  const radius = 70
  const circumference = Math.PI * radius  // half circle
  const offset = circumference - (score / 100) * circumference

  return (
    <div className="flex flex-col items-center py-4">
      <svg width="200" height="110" viewBox="0 0 200 110">
        {/* Background arc */}
        <path
          d="M 20 100 A 80 80 0 0 1 180 100"
          fill="none" stroke="#e5e7eb" strokeWidth="16" strokeLinecap="round"
        />
        {/* Filled arc */}
        <path
          d="M 20 100 A 80 80 0 0 1 180 100"
          fill="none"
          stroke={color}
          strokeWidth="16"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 0.8s ease, stroke 0.4s ease" }}
        />
        {/* Score text */}
        <text x="100" y="90" textAnchor="middle" fontSize="28" fontWeight="bold" fill={color}>
          {score}
        </text>
        <text x="100" y="108" textAnchor="middle" fontSize="10" fill="#9ca3af">
          /100
        </text>
      </svg>
      <span className="text-sm font-semibold mt-1 capitalize" style={{ color }}>
        {label}
      </span>
    </div>
  )
}
```

---

## /api/validate/route.ts

```typescript
import { NextRequest, NextResponse } from "next/server"

const REST_BRIDGE_URL = process.env.REST_BRIDGE_URL ?? "http://localhost:8001"

export async function POST(req: NextRequest) {
  const body = await req.json()
  
  const res = await fetch(`${REST_BRIDGE_URL}/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  
  if (!res.ok) {
    return NextResponse.json({ error: "Backend error" }, { status: 502 })
  }
  
  return NextResponse.json(await res.json())
}
```

---

## base.py (Abstract Scanner)

```python
from abc import ABC, abstractmethod
import httpx
from models import ScanResult

class BaseScanner(ABC):
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=4.0,
            headers={
                "User-Agent": "paraguay-idea-mcp/0.1.0 (research; contact@example.com)",
                "Accept": "application/json, text/html",
            },
            follow_redirects=True
        )
    
    @abstractmethod
    async def scan(self, keywords: list[str]) -> ScanResult:
        pass
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        await self.client.aclose()
```

---

## README Demo Cases to include

```markdown
## Casos de demo

### Caso 1 — Mercado saturado
```
idea = "App de delivery de comida en Asunción"
```
Expected: market_signal ~70-80
TuRuc returns: 200+ empresas en gastronomía/delivery
Recommendation: pivot a ciudades del interior o segmento B2B (catering empresas)

### Caso 2 — Oportunidad real
```
idea = "Software de gestión para cooperativas agropecuarias del interior"
```
Expected: market_signal ~30-45
TuRuc: pocas empresas específicamente en software para cooperativas
Recommendation: nicho válido, demanda estatal confirma sector

### Caso 3 — Easter egg del demo
```
idea = "Herramienta para validar ideas de startups en el mercado paraguayo"
```
Expected: market_signal ~5-15
0 competidores directos en TuRuc
0 cobertura de prensa específica
Recommendation: "Espacio completamente abierto. Estás construyendo exactamente esto ahora."
```

---

## Execution Checklist

Generate files in this order:
1. models.py
2. keyword_extractor.py  
3. scanners/base.py
4. scanners/turuc_scanner.py
5. scanners/google_news_scanner.py
6. scanners/dncp_scanner.py
7. scanners/mic_scraper.py
8. scorer.py
9. tools.py
10. server.py
11. rest_bridge.py
12. pyproject.toml + .env.example
13. frontend/ (all files)
14. README.md

After generating all files, verify that these commands work:

```bash
# Terminal 1 — Python backend
pip install -e ".[dev]"
uvicorn rest_bridge:app --port 8001 --reload

# Terminal 2 — Next.js frontend  
cd frontend && npm install && npm run dev

# Quick smoke test
curl -X POST http://localhost:8001/validate \
  -H "Content-Type: application/json" \
  -d '{"idea": "software para cooperativas", "depth": "quick"}'
```

The smoke test must return valid JSON with market_signal as integer 0-100.
All scanners must handle timeouts and API errors gracefully — never throw,
always return partial ScanResult with available=False if a source fails.
```

***

Pegalo directo en Claude Code con el directorio vacío. Los puntos clave del cambio vs la versión anterior:

- **TuRuc** sigue siendo la fuente principal — API pública sin auth, datos live [docs.turuc.com](https://docs.turuc.com.py/docs/api/table-contribuyentes)
- **DNCP** ahora tiene el flow OAuth correcto con `.env` graceful fallback [contrataciones.gov](https://www.contrataciones.gov.py/datos/api/v2/)
- **MIC** se scrapea con BeautifulSoup en tiempo real, no CSV [portalemprendedor.mic.gov](https://portalemprendedor.mic.gov.py/convocatoria.php?id=16)
- **Google News RSS Paraguay** reemplaza el CSV del MIC como cuarta fuente — 0 dependencias, datos del día
- El `rest_bridge.py` desacopla el frontend del protocolo MCP, haciéndolo desplegable en Vercel sin cambios
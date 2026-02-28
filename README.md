# Paraguay Startup Validator — MCP

> Validá tu idea de startup contra datos reales del mercado paraguayo **antes de escribir una sola línea de código**.

---

## El problema que resuelve

Los agentes de IA (como Claude, GPT, etc.) tienen un defecto crítico: **empiezan a construir sin validar**.

```
Usuario:  "Haceme una app de delivery para Paraguay"
Agente:   "¡Genial! Acá te dejo el código..."
Realidad: Hay 200+ empresas de delivery registradas en el DNIT 🤦
```

Este proyecto conecta un **servidor MCP** con fuentes de datos reales del gobierno paraguayo para que el agente **verifique primero, construya después**.

---

## Cómo funciona el sistema

```
┌─────────────────────────────────────────────────────────────┐
│                        USUARIO                              │
│        "Quiero hacer una fintech para cooperativas"         │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                   AGENTE (OpenClaw / Claude)                 │
│                                                             │
│  Antes de responder, llama automáticamente a:               │
│  ┌─────────────────────────────────────────┐               │
│  │  validate_idea("fintech cooperativas")  │               │
│  └─────────────────────────────────────────┘               │
└───────────────────┬─────────────────────────────────────────┘
                    │  MCP tool call (stdio / HTTP)
                    ▼
┌─────────────────────────────────────────────────────────────┐
│              PARAGUAY IDEA MCP SERVER                       │
│                                                             │
│  LLM extrae keywords → ["fintech", "cooperativa", "pagos"] │
│                                                             │
│  Corre los 5 scanners EN PARALELO:                        │
│                                                             │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │    TuRuc     │ │ Google News  │ │     DNCP     │        │
│  │  (empresas   │ │  (prensa     │ │  (compras    │        │
│  │   DNIT)      │ │  paraguaya)  │ │   estado)    │        │
│  └──────────────┘ └──────────────┘ └──────────────┘        │
│         +                                                   │
│  ┌──────────────┐ ┌──────────────┐                           │
│  │     MIC     │ │   Web PY     │                           │
│  │  (startups) │ │ (DDG, pymes) │                           │
│  └──────────────┘ └──────────────┘                           │
│                                                             │
│  scorer.py → market_signal: 35/100                         │
└───────────────────┬─────────────────────────────────────────┘
                    │  JSON result
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                   AGENTE (OpenClaw / Claude)                 │
│                                                             │
│  market_signal = 35 → "oportunidad con diferenciación"     │
│  → Sugiere nicho específico, no bloquea la construcción     │
└─────────────────────────────────────────────────────────────┘
```

---

## Las 4 fuentes de datos

| Scanner | Fuente | Qué mide | Auth |
|---|---|---|---|
| **TuRuc** | `turuc.com.py/api` | Empresas registradas en DNIT por rubro | Ninguna |
| **Google News** | RSS de Google News Paraguay | Cobertura de prensa del sector | Ninguna |
| **MIC** | Portal Emprendedor MIC | Startups registradas en el ministerio | Ninguna |
| **DNCP** | `contrataciones.gov.py` | Cuánto compra el Estado en ese sector | OAuth2 (opcional) |

### Cómo se calcula el puntaje

```
market_signal (0-100) =

  TuRuc   × 50%   ← densidad de empresas (señal principal)
+ MIC     × 30%   ← competidores startups directos
+ Prensa  × 15%   ← conocimiento del mercado
- DNCP    × 20%   ← descuento si el Estado compra = oportunidad
```

### Qué significa el puntaje

```
  0 ──────────── 30 ──────────────── 70 ──────── 100
  │                │                  │              │
  │  ESPACIO       │  OPORTUNIDAD     │  MERCADO     │
  │  ABIERTO 🟦   │  CON NICHO 🟥   │  SATURADO ⬜ │
  │                │                  │              │
  │  Construí ya   │  Diferenciá      │  Pivotá      │
  │  sin problema  │  antes de lanzar │  o buscá     │
  │                │                  │  otro ángulo │
```

---

## Estructura del proyecto

```
startup-validator/
│
├── server.py              ← Entry point MCP (stdio transport)
├── rest_bridge.py         ← FastAPI en :8001 (para el frontend)
├── tools.py               ← @mcp.tool() validate_idea()
├── scorer.py              ← Fórmula de scoring
├── models.py              ← Tipos Pydantic (ScanResult, etc.)
├── ai_analyzer.py         ← LLM: keywords + análisis de mercado
│
├── scanners/
│   ├── base.py            ← BaseScanner abstracta
│   ├── turuc_scanner.py   ← DNIT/TuRuc API
│   ├── google_news_scanner.py
│   ├── dncp_scanner.py
│   └── mic_scraper.py
│
└── frontend/              ← Next.js 15 + Tailwind
    ├── app/
    │   ├── page.tsx
    │   └── api/validate/route.ts   ← proxy a :8001
    └── components/
        ├── IdeaValidatorPanel.tsx
        ├── SignalGauge.tsx          ← gauge SVG, colores bandera PY
        ├── CompetitorCard.tsx
        └── MetricCard.tsx
```

---

## Cómo usar con OpenClaw

OpenClaw es un agente de IA que tiene acceso a este servidor MCP. Al configurarlo, cada vez que alguien le pida construir algo, **el agente valida primero**.

### 1. Registrá el MCP server en OpenClaw

```json
{
  "mcpServers": {
    "paraguay-idea-mcp": {
      "command": "uv",
      "args": ["run", "python", "server.py"],
      "cwd": "/ruta/a/startup-validator"
    }
  }
}
```

### 2. Pegá las instrucciones del agente

Creá un archivo `agent.instructions.md` y cargalo en OpenClaw:

```
Antes de sugerir, diseñar o construir cualquier startup, producto,
feature o herramienta, SIEMPRE ejecutá validate_idea primero.

Si market_signal > 70 → DETENTE, reportá competidores, sugerí 2 pivots.
Si market_signal 30-70 → Mostrá resultados, sugerí nicho diferenciado.
Si market_signal < 30  → Procedé a construir directamente.
```

### 3. El flujo en acción

```
Vos:      "Quiero hacer una app de delivery en Asunción"

OpenClaw: [llama a validate_idea internamente]
          ⚡ Escaneando TuRuc, Google News...

          market_signal: 78/100 — mercado saturado

          Encontré 340 empresas en gastronomía/delivery en el DNIT.
          Top competidores: PedidosYa PY (RUC: 80012345), Hugo App...

          ⚠️  Este mercado está muy cubierto en Asunción.

          Dos pivots con oportunidad real:
          1. Ciudad del Este / Encarnación — 80% menos competencia
          2. Delivery B2B para empresas y caterings corporativos

          ¿Querés explorar alguno de estos ángulos?
```

---

## Correr el proyecto

### Backend

```bash
# Crear entorno e instalar dependencias
uv venv
uv add fastmcp httpx beautifulsoup4 lxml pydantic python-dotenv fastapi uvicorn

# Levantar el REST bridge para el frontend
uv run uvicorn rest_bridge:app --port 8001 --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

### Variables de entorno (opcionales)

```bash
cp .env.example .env
# Editá .env para agregar DNCP_REQUEST_TOKEN si tenés credenciales DNCP
```

---

## Casos de demo para la hackathon

### Caso 1 — Mercado saturado (signal ~75)
```
"App de delivery de comida en Asunción"
→ 200+ empresas en DNIT, pivot sugerido al interior del país
```

### Caso 2 — Oportunidad con nicho (signal ~35)
```
"Software de gestión para cooperativas agropecuarias del interior"
→ Pocas empresas directas, demanda DNCP confirma sector
```

### Caso 3 — Easter egg del demo (signal ~5)
```
"Herramienta para validar ideas de startups en el mercado paraguayo"
→ 0 competidores. El agente responde:
   "Espacio completamente abierto. Estás construyendo exactamente esto ahora."
```

---

## Stack técnico

| Capa | Tecnología |
|---|---|
| MCP Server | FastMCP 2.0+, Python 3.11+, stdio transport |
| HTTP async | httpx 0.27+ |
| Scraping | BeautifulSoup4 + lxml |
| Modelos | Pydantic v2 |
| REST Bridge | FastAPI + uvicorn |
| Frontend | Next.js 15, TypeScript, Tailwind CSS |
| Package manager | uv |

---

*Construido en 5 horas para la hackathon — datos 100% reales, cero CSVs.*

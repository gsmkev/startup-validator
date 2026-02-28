"""
FastAPI server on port 8001.

Exposes three interfaces:
  - REST  POST /validate       ← Next.js frontend (IdeaValidatorPanel) calls this
  - REST  POST /agent          ← Next.js frontend (ChatPanel) — OpenClaw-style agent loop
  - MCP        /mcp            ← OpenClaw (via openclaw-mcp-client plugin) — StreamableHTTP

Run with: uvicorn rest_bridge:app --port 8001 --reload
"""
from dotenv import load_dotenv
load_dotenv()

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import AsyncOpenAI
from scanners import get_source_labels
from tools import validate_idea, mcp

app = FastAPI(title="Paraguay Idea Validator")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# ── OpenAI client pointing at OpenRouter ────────────────────────────────────

def _openrouter_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY", ""),
    )

_AGENT_MODEL = "openai/gpt-4o-mini"

def _system_prompt() -> str:
    sources = ", ".join(get_source_labels())
    return (
        f"Sos un agente experto en el mercado paraguayo. Te van a dar datos reales de validación "
        f"de una idea de startup (obtenidos de {sources}) y tenés que explicarlos "
        f"de forma clara y accionable en 3-5 párrafos cortos. Usá español rioplatense. Sé directo y específico."
    )


# ── REST bridge for the Next.js frontend ────────────────────────────────────

class ValidateRequest(BaseModel):
    idea: str
    depth: str = "deep"


@app.post("/validate")
async def validate(req: ValidateRequest):
    return await validate_idea(req.idea, req.depth)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "paraguay-idea-mcp", "mcp_endpoint": "/mcp"}


# ── Agent endpoint — OpenClaw-style conversation loop ───────────────────────

class Message(BaseModel):
    role: str
    content: str

class AgentRequest(BaseModel):
    messages: list[Message]


@app.post("/agent")
async def agent(req: AgentRequest):
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        return {
            "role": "assistant",
            "content": "⚠️ Configurá OPENROUTER_API_KEY en el .env del backend para usar el agente."
        }

    # Extract the latest user idea
    idea = next((m.content for m in reversed(req.messages) if m.role == "user"), "")
    if not idea:
        return {"role": "assistant", "content": "Contame tu idea de startup."}

    data = await validate_idea(idea, depth="deep")

    # ── Step 2: build a compact context for the LLM (avoid large JSON) ─────
    score      = data["market_signal"]
    label      = data["signal_label"]
    sources    = ", ".join(data["sources_queried"]) or "ninguna"
    competitors = ", ".join(c["name"] for c in data["competitors"][:3]) or "ninguno"
    strengths  = "\n".join(f"- {s}" for s in data["strengths"][:3])
    weaknesses = "\n".join(f"- {w}" for w in data["weaknesses"][:3])
    actions    = "\n".join(f"{i+1}. {a}" for i, a in enumerate(data["action_items"][:3]))
    pivots     = "\n".join(f"- {p}" for p in data["pivot_suggestions"][:2])

    context = f"""Idea analizada: "{idea}"
Señal de mercado: {score}/100 — {label}
Fuentes consultadas: {sources}
Competidores encontrados: {competitors}

Fortalezas detectadas:
{strengths or "- Ninguna registrada"}

Riesgos:
{weaknesses or "- Ninguno detectado"}

Próximos pasos sugeridos:
{actions or "- Validar con potenciales clientes"}

Pivots disponibles:
{pivots or "- Explorar nichos del interior del país"}"""

    # ── Step 3: ask OpenRouter to explain it in natural language ────────────
    try:
        client = _openrouter_client()
        response = await client.chat.completions.create(
            model=_AGENT_MODEL,
            messages=[
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": context},
            ],
            extra_headers={
                "HTTP-Referer": "https://github.com/paraguay-idea-mcp",
                "X-OpenRouter-Title": "Paraguay Startup Validator",
            },
        )
        reply = response.choices[0].message.content or ""
        return {"role": "assistant", "content": reply}

    except Exception as e:
        err = str(e)
        if "429" in err or "rate" in err.lower():
            # Fallback: return a structured text summary without LLM
            emoji = "🔴" if score > 70 else "🟡" if score > 30 else "🟢"
            fallback = (
                f"{emoji} **{label.upper()}** — {score}/100\n\n"
                f"**Fuentes:** {sources}\n"
                f"**Competidores:** {competitors}\n\n"
                f"**Fortalezas:**\n{strengths or '—'}\n\n"
                f"**Riesgos:**\n{weaknesses or '—'}\n\n"
                f"**Próximos pasos:**\n{actions}\n\n"
                f"*(Resumen automático — OpenRouter rate limit, reintentá en unos segundos)*"
            )
            return {"role": "assistant", "content": fallback}
        if "401" in err or "authentication" in err.lower():
            return {"role": "assistant", "content": "⚠️ OPENROUTER_API_KEY inválida."}
        return {"role": "assistant", "content": f"⚠️ Error: {err}"}


# ── MCP StreamableHTTP endpoint for OpenClaw ────────────────────────────────

app.mount("/mcp", mcp.http_app(transport="http"))

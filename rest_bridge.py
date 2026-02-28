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

import logging
import os

from logging_config import configure_logging

configure_logging()
logger = logging.getLogger("validator.api")
logger.info("Paraguay Startup Validator starting")

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
        f"Sos un analista experto del mercado paraguayo. Te van a dar datos reales de validación "
        f"de una idea de startup (obtenidos de {sources}). Tu tarea es producir un análisis completo y técnico.\n\n"
        f"OBLIGATORIO:\n"
        f"1. Incluí un análisis FODA completo: Fortalezas, Oportunidades, Debilidades, Amenazas del mercado.\n"
        f"2. Analizá la competencia: mencioná por nombre a cada competidor relevante con su fuente (TuRuc, Ecommerce, etc.). "
        f"Si hay muchos (ej. 46 en marketplaces), agrupá por tipo y citá ejemplos concretos.\n"
        f"3. Usá TODAS las fuentes disponibles: los conteos por fuente (DNCP, Ecommerce PY, Google News, etc.) "
        f"son datos reales — explicalos en el análisis.\n"
        f"4. SESGO DE API: Si una fuente aparece en 'Fuentes no disponibles' (ej. DNCP 401, SET DNS), "
        f"NO concluyas que 'no existen empresas' o 'el mercado está vacío' solo por eso. "
        f"Explicá que ese dato podría no estar disponible por error técnico.\n"
        f"5. Sé técnico y detallado: referencias concretas a números, fuentes y competidores.\n"
        f"Respondé en español rioplatense. 4-6 párrafos bien estructurados."
    )


# ── REST bridge for the Next.js frontend ────────────────────────────────────

class ValidateRequest(BaseModel):
    idea: str
    depth: str = "deep"


@app.post("/validate")
async def validate(req: ValidateRequest):
    logger.info("POST /validate idea=%r depth=%s", req.idea[:80], req.depth)
    result = await validate_idea(req.idea, req.depth)
    logger.info("validate done: score=%s sources=%s", result.get("market_signal"), result.get("sources_queried"))
    return result


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
    logger.info("POST /agent messages_count=%d", len(req.messages))
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        logger.warning("agent: OPENROUTER_API_KEY not set")
        return {
            "role": "assistant",
            "content": "⚠️ Configurá OPENROUTER_API_KEY en el .env del backend para usar el agente."
        }

    messages = req.messages
    idea = next((m.content for m in reversed(messages) if m.role == "user"), "")
    if not idea:
        return {"role": "assistant", "content": "Contame tu idea de startup."}

    # Follow-up detection: skip full scan if this looks like a short follow-up
    user_msgs = [m for m in messages if m.role == "user"]
    is_followup = (
        len(user_msgs) >= 2
        and len(idea.strip()) < 80
        and any(
            p in idea.lower()
            for p in (
                "¿", "?", "explic", "más", "detalle", "y qué", "como", "cuál",
                "por qué", "mejor", "peor", "recomend", "suger",
            )
        )
    )
    if is_followup and len(messages) >= 3:
        logger.info("agent: follow-up detected, skipping full scan")
        # Use conversation history; LLM answers from prior context (no re-scan)
        try:
            client = _openrouter_client()
            conv = [{"role": m.role, "content": m.content} for m in messages[-6:]]
            conv.insert(
                0,
                {
                    "role": "system",
                    "content": (
                        _system_prompt()
                        + " El usuario hace una pregunta de seguimiento. "
                        "Respondé basándote en el contexto previo de la conversación."
                    ),
                },
            )
            response = await client.chat.completions.create(
                model=_AGENT_MODEL,
                messages=conv,
                extra_headers={
                    "HTTP-Referer": "https://github.com/paraguay-idea-mcp",
                    "X-OpenRouter-Title": "Paraguay Startup Validator",
                },
            )
            return {"role": "assistant", "content": response.choices[0].message.content or ""}
        except Exception as e:
            logger.warning("agent: follow-up LLM failed, falling back to full scan: %s", e)

    logger.info("agent: running full validate_idea idea=%r", idea[:80])
    data = await validate_idea(idea, depth="deep")

    # ── Step 2: build rich context for the LLM ─────────────────────────────
    score = data["market_signal"]
    label = data["signal_label"]
    sources_ok = ", ".join(data["sources_queried"]) or "ninguna"
    sources_failed = data.get("sources_unavailable", [])
    source_counts = data.get("source_counts", {})

    comp_lines = []
    for c in data["competitors"][:10]:
        parts = [f"- {c.get('name', '?')} ({c.get('source', '?')})"]
        if c.get("detail"):
            parts.append(f" — {str(c['detail'])[:80]}")
        if c.get("url"):
            parts.append(f" | URL: {c['url'][:60]}")
        comp_lines.append("".join(parts))
    competitors_block = "\n".join(comp_lines) if comp_lines else "Ninguno detectado en las fuentes consultadas."

    counts_block = "\n".join(f"  - {k}: {v}" for k, v in source_counts.items()) if source_counts else "Sin datos"
    failed_block = ", ".join(str(s)[:50] for s in sources_failed[:5]) if sources_failed else "Ninguna"

    strengths = "\n".join(f"- {s}" for s in data["strengths"])
    weaknesses = "\n".join(f"- {w}" for w in data["weaknesses"])
    actions = "\n".join(f"{i+1}. {a}" for i, a in enumerate(data["action_items"]))
    pivots = "\n".join(f"- {p}" for p in data["pivot_suggestions"])
    ai_rec = data.get("ai_recommendation", "")
    quick_wins = "\n".join(f"- {w}" for w in data.get("quick_wins", []))
    red_flags = "\n".join(f"- {r}" for r in data.get("red_flags", []))

    context = f"""Idea analizada: "{idea}"

Señal de mercado: {score}/100 — {label}

Resultados por fuente (datos reales consultados):
{counts_block}

Fuentes consultadas OK: {sources_ok}
Fuentes no disponibles (error API/auth): {failed_block}

Competencia encontrada (nombre, fuente, detalle):
{competitors_block}

Fortalezas del mercado:
{strengths or "- Ninguna detectada"}

Debilidades / riesgos:
{weaknesses or "- Ninguno detectado"}

Amenazas (a considerar):
{red_flags or "- Ninguna específica"}

Próximos pasos sugeridos:
{actions or "- Validar con potenciales clientes"}

Pivots sugeridos:
{pivots or "- Explorar nichos del interior"}

Quick wins (90 días):
{quick_wins or "- Definir MVP y primeros clientes"}

Análisis AI previo (integrar en tu respuesta):
{ai_rec or "- Sin análisis adicional"}"""

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
        logger.info("agent: LLM reply len=%d", len(reply))
        return {"role": "assistant", "content": reply}

    except Exception as e:
        logger.warning("agent: LLM error %s", e)
        err = str(e)
        if "429" in err or "rate" in err.lower():
            # Fallback: return a structured text summary without LLM
            emoji = "🔴" if score > 70 else "🟡" if score > 30 else "🟢"
            comp_summary = ", ".join(c.get("name", "?") for c in data["competitors"][:5]) or "ninguno"
            fallback = (
                f"{emoji} **{label.upper()}** — {score}/100\n\n"
                f"**Fuentes OK:** {sources_ok}\n"
                f"**Fuentes fallidas:** {failed_block}\n"
                f"**Competidores:** {comp_summary}\n\n"
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

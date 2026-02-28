"""
OpenRouter AI analysis layer using OpenAI SDK + Instructor for validated structured output.
Model: openai/gpt-4o-mini via openrouter.ai

Provides:
  - extract_keywords_via_llm: LLM extracts search keywords from user idea
  - generate_ai_analysis: AI-powered market analysis

If OPENROUTER_API_KEY is not set, keyword extraction falls back to simple tokenization.
"""
from __future__ import annotations

import re
import os
from typing import TYPE_CHECKING

import instructor
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from models import Competitor


class KeywordExtraction(BaseModel):
    keywords: list[str] = Field(
        min_length=1,
        max_length=6,
        description="1-6 search terms or short phrases for finding businesses in Paraguay",
    )


class AIAnalysis(BaseModel):
    ai_recommendation: str = Field(
        description="Recomendación personalizada (2-3 oraciones) basada en datos reales del mercado paraguayo"
    )
    quick_wins: list[str] = Field(
        min_length=3,
        max_length=3,
        description="Exactamente 3 acciones concretas para los primeros 90 días en Paraguay"
    )
    red_flags: list[str] = Field(
        min_length=2,
        max_length=3,
        description="2-3 riesgos reales y específicos del contexto paraguayo (regulación, cultura, infraestructura)"
    )


def _make_client(api_key: str) -> instructor.AsyncInstructor:
    openai_client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )
    return instructor.from_openai(openai_client)


def _fallback_keywords(idea: str) -> list[str]:
    """Simple tokenization when LLM is unavailable."""
    tokens = re.findall(r"\b[a-záéíóúüñ]{4,}\b", idea.lower())
    stop = {"para", "como", "este", "esta", "tipo", "hacer", "quiero"}
    filtered = [t for t in tokens if t not in stop]
    return list(dict.fromkeys(filtered))[:5] or [idea[:50]]


async def extract_keywords_via_llm(idea: str) -> list[str]:
    """
    Use LLM to extract 3-6 search keywords from the user's idea for use in
    TuRuc, DNCP, web scraper, etc. Falls back to simple tokenization if no API key.
    """
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        return _fallback_keywords(idea)

    try:
        client = _make_client(api_key)
        result: KeywordExtraction = await client.chat.completions.create(
            model="openai/gpt-4o-mini",
            response_model=KeywordExtraction,
            extra_headers={
                "HTTP-Referer": "https://github.com/paraguay-idea-mcp",
                "X-OpenRouter-Title": "Paraguay Startup Validator",
            },
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Sos un experto en mercados paraguayos. Tu tarea es extraer "
                        "términos de búsqueda (keywords) de una idea de negocio/startup. "
                        "Los términos se usarán para buscar empresas, competidores y datos "
                        "en registros (DNIT, DNCP) y buscadores web. Incluí: sectores, "
                        "productos, servicios, nichos. Ejemplo: 'franquicia de heladería' "
                        "→ heladería, franquicia, helado, gastronomía."
                    ),
                },
                {"role": "user", "content": f"Idea del usuario: {idea}"},
            ],
            max_retries=2,
        )
        return result.keywords[:6]
    except Exception:
        return _fallback_keywords(idea)


def _build_sources_block(source_counts: dict[str, int]) -> str:
    if not source_counts:
        return ""
    lines = [f"  - {name}: {count}" for name, count in source_counts.items()]
    return "\nResultados por fuente:\n" + "\n".join(lines)


def _build_competitors_block(competitors: list[Competitor]) -> str:
    if not competitors:
        return ""
    lines: list[str] = []
    for c in competitors[:5]:
        entry = f"  - {c.name} ({c.source})"
        if c.detail:
            entry += f" — {c.detail[:120]}"
        lines.append(entry)
    return "\nCompetidores principales detectados:\n" + "\n".join(lines)


async def generate_ai_analysis(
    idea: str,
    keywords: list[str],
    score: int,
    label: str,
    source_counts: dict[str, int],
    competitors: list[Competitor],
    news_titles: list[str],
) -> dict:
    """
    Returns dict with ai_recommendation, quick_wins, red_flags.
    Returns empty dict if OPENROUTER_API_KEY is missing or the call fails.
    """
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        return {}

    news_block = ""
    if news_titles:
        news_block = "\nTitulares de prensa recientes:\n" + "\n".join(f"  - {t}" for t in news_titles[:3])

    prompt = (
        f"Sos un analista experto del ecosistema emprendedor paraguayo con conocimiento "
        f"profundo del DNIT, DNCP, MIC y el mercado local.\n\n"
        f"Analizá esta idea de startup:\n"
        f"Idea: {idea}\n"
        f"Keywords del sector: {', '.join(keywords)}\n"
        f"Señal de mercado: {score}/100 ({label})"
        f"{_build_sources_block(source_counts)}"
        f"{_build_competitors_block(competitors)}"
        f"{news_block}\n\n"
        f"Basándote en los competidores concretos listados arriba, explicá cómo "
        f"diferenciarse de ellos. Si no hay competidores, enfocate en cómo validar "
        f"la demanda real."
    )

    try:
        client = _make_client(api_key)
        result: AIAnalysis = await client.chat.completions.create(
            model="openai/gpt-4o-mini",
            response_model=AIAnalysis,
            extra_headers={
                "HTTP-Referer": "https://github.com/paraguay-idea-mcp",
                "X-OpenRouter-Title": "Paraguay Startup Validator",
            },
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Sos un analista experto del mercado paraguayo. "
                        "Respondé siempre en español rioplatense. "
                        "Sé específico y concreto — mencioná competidores reales "
                        "por nombre cuando los tengas. Evitá consejos genéricos."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_retries=2,
        )
        return result.model_dump()
    except Exception:
        return {}

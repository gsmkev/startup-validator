"""
OpenRouter AI analysis layer using OpenAI SDK + Instructor for validated structured output.
Model: openai/gpt-4o-mini via openrouter.ai

Provides:
  - extract_keywords_via_llm: LLM extracts search keywords from user idea
  - generate_ai_analysis: AI-powered market analysis

If OPENROUTER_API_KEY is not set, keyword extraction falls back to simple tokenization.
"""
from __future__ import annotations

import logging
import os
import re
from typing import TYPE_CHECKING

logger = logging.getLogger("validator.ai")

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
        description="Análisis completo: FODA (Fortalezas, Oportunidades, Debilidades, Amenazas), análisis de competencia por nombre, recomendaciones. 4-6 párrafos técnicos y detallados"
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
    Results cached 15 min by idea.
    """
    try:
        from cache import get_cached_keywords, set_cached_keywords
        cached = get_cached_keywords(idea)
        if cached is not None:
            logger.debug("extract_keywords cache HIT")
            return cached
    except ImportError:
        pass

    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        logger.info("extract_keywords: no API key, using fallback")
        return _fallback_keywords(idea)

    logger.info("extract_keywords: calling LLM for idea=%r", idea[:60])

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
        keywords = result.keywords[:6]
        logger.info("extract_keywords: LLM returned %s", keywords)
        try:
            from cache import set_cached_keywords
            set_cached_keywords(idea, keywords)
        except ImportError:
            pass
        return keywords
    except Exception as e:
        logger.warning("extract_keywords LLM failed: %s, using fallback", e)
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
    for c in competitors[:10]:
        entry = f"  - {c.name} ({c.source})"
        if c.detail:
            entry += f" — {c.detail[:120]}"
        if c.url:
            entry += f" | {c.url[:50]}"
        lines.append(entry)
    return "\nCompetidores detectados (nombre, fuente, detalle):\n" + "\n".join(lines)


async def generate_ai_analysis(
    idea: str,
    keywords: list[str],
    score: int,
    label: str,
    source_counts: dict[str, int],
    competitors: list[Competitor],
    news_titles: list[str],
    sources_unavailable: list[str] | None = None,
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
        news_block = "\nTitulares de prensa recientes:\n" + "\n".join(f"  - {t}" for t in news_titles[:5])

    failed_block = ""
    if sources_unavailable:
        failed_block = (
            "\nFuentes NO disponibles (error API/auth/DNS — NO asumir que 'no hay datos'): "
            + ", ".join(str(s)[:40] for s in sources_unavailable[:6])
            + "\n"
        )

    prompt = (
        f"Analizá esta idea de startup con un enfoque técnico y completo:\n\n"
        f"Idea: {idea}\n"
        f"Keywords: {', '.join(keywords)}\n"
        f"Señal de mercado: {score}/100 ({label})\n"
        f"{_build_sources_block(source_counts)}"
        f"{_build_competitors_block(competitors)}"
        f"{news_block}"
        f"{failed_block}\n"
        f"Tu análisis debe incluir:\n"
        f"1. FODA: Fortalezas, Oportunidades, Debilidades, Amenazas del mercado para esta idea.\n"
        f"2. Análisis de competencia: mencioná por nombre a los competidores listados, agrupá por fuente "
        f"(ej. 46 en Ecommerce, 5 en Google News). Si hay muchos, citá ejemplos representativos.\n"
        f"3. Si DNCP, MIC, SET u otra fuente aparece en 'no disponibles', NO concluyas que 'no existen empresas' "
        f"solo por eso — podría ser error de API o autenticación.\n"
        f"4. Recomendaciones concretas y diferenciación versus la competencia encontrada."
    )

    logger.info("generate_ai_analysis: calling LLM score=%d", score)
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
                        "Sos un analista técnico del mercado paraguayo. Producí análisis completos y detallados. "
                        "Incluí siempre FODA y análisis de competencia por nombre. "
                        "No te bases en ausencia de datos de fuentes fallidas (DNCP 401, SET DNS, etc.). "
                        "Respondé en español rioplatense. 4-6 párrafos bien estructurados."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_retries=2,
        )
        logger.info("generate_ai_analysis: got ai_recommendation len=%d", len(result.ai_recommendation))
        return result.model_dump()
    except Exception as e:
        logger.warning("generate_ai_analysis failed: %s", e)
        return {}

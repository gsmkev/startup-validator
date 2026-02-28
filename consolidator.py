"""
OpenRouter consolidation layer for skill results.

Takes raw ScanResults from all skills and produces a unified analysis
via Claude Haiku. Used by validate_idea_v2.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("validator.consolidator")

import instructor
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

_CONSOLIDATOR_MODEL = "anthropic/claude-3.5-haiku"


@dataclass
class SkillResult:
    skill_name: str
    data: dict[str, Any]
    error: str | None = None
    duration_ms: int = 0


class ConsolidatedReview(BaseModel):
    """LLM-produced analysis from all skill results."""
    strengths: list[str] = Field(
        description="2-4 fortalezas del mercado para esta idea",
    )
    weaknesses: list[str] = Field(
        description="2-4 riesgos o debilidades detectados",
    )
    action_items: list[str] = Field(
        min_length=3,
        max_length=5,
        description="3-5 acciones concretas para los próximos 90 días",
    )
    pivot_suggestions: list[str] = Field(
        min_length=2,
        max_length=4,
        description="2-4 pivots sugeridos si el mercado está saturado o hay nicho",
    )


def _format_skill_data(skill_name: str, data: dict[str, Any]) -> str:
    """Format a ScanResult dict for the consolidator context."""
    if data.get("available") is False:
        return f"Fuente no disponible: {data.get('hints', ['error'])[:1]}"
    count = data.get("count", 0)
    comps = data.get("competitors", [])[:5]
    comp_str = ", ".join(c.get("name", "?") for c in comps) if comps else "ninguno"
    hints = data.get("hints", [])
    hint_str = "; ".join(hints[:2]) if hints else ""
    parts = [f"count={count}", f"competidores: {comp_str}"]
    if hint_str:
        parts.append(f"hints: {hint_str}")
    return "\n".join(parts)


async def consolidate_via_openrouter(
    idea: str,
    keywords: list[str],
    score: int,
    label: str,
    recommendation: str,
    skill_results: list[SkillResult],
) -> dict:
    """
    Send skill results to OpenRouter for unified analysis.
    Returns dict with strengths, weaknesses, action_items, pivot_suggestions.
    """
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        logger.warning("consolidate: no OPENROUTER_API_KEY")
        return {
            "strengths": [],
            "weaknesses": [],
            "action_items": [],
            "pivot_suggestions": [],
        }

    skill_summaries = []
    for sr in skill_results:
        if sr.error:
            skill_summaries.append(f"[{sr.skill_name}] ERROR: {sr.error}")
        else:
            summary = _format_skill_data(sr.skill_name, sr.data)
            skill_summaries.append(f"[{sr.skill_name}] ({sr.duration_ms}ms)\n{summary}")

    context = "\n\n".join(skill_summaries)
    system_prompt = (
        "Sos un analista experto del ecosistema emprendedor paraguayo. "
        "Te pasan datos crudos de múltiples fuentes (TuRuc, DNCP, MIC, Web, etc.) "
        "para una idea de startup. Tu tarea es producir un análisis unificado: "
        "fortalezas, debilidades, próximos pasos concretos y pivots sugeridos. "
        "Incluí análisis FODA y competencia por nombre. "
        "Si una fuente aparece como 'ERROR' o 'no disponible', NO concluyas que "
        "'no existen empresas' o 'el mercado está vacío' solo por eso — puede ser error de API. "
        "Respondé en español rioplatense. Sé específico y técnico."
    )
    user_content = (
        f"Idea: {idea}\n"
        f"Keywords: {keywords}\n"
        f"Señal de mercado: {score}/100 — {label}\n"
        f"Recomendación base: {recommendation}\n\n"
        f"Datos por fuente:\n{context}"
    )

    logger.info("consolidate: calling OpenRouter %s with %d skill results", _CONSOLIDATOR_MODEL, len(skill_results))
    try:
        client = instructor.from_openai(
            AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key),
        )
        result: ConsolidatedReview = await client.chat.completions.create(
            model=_CONSOLIDATOR_MODEL,
            response_model=ConsolidatedReview,
            extra_headers={
                "HTTP-Referer": "https://github.com/paraguay-idea-mcp",
                "X-OpenRouter-Title": "Paraguay Startup Validator",
            },
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            max_retries=2,
        )
        logger.info("consolidate: got %d strengths %d action_items", len(result.strengths), len(result.action_items))
        return result.model_dump()
    except Exception as e:
        logger.warning("consolidate failed: %s", e)
        return {
            "strengths": [],
            "weaknesses": [],
            "action_items": [],
            "pivot_suggestions": [],
        }

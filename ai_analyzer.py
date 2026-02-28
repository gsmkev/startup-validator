"""
OpenRouter AI analysis layer using OpenAI SDK + Instructor for validated structured output.
Model: openai/gpt-4o-mini via openrouter.ai

If OPENROUTER_API_KEY is not set, returns empty dict silently.
"""
import os
import instructor
from openai import AsyncOpenAI
from pydantic import BaseModel, Field


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


async def generate_ai_analysis(
    idea: str,
    keywords: list[str],
    score: int,
    label: str,
    turuc_count: int,
    dncp_count: int,
    news_titles: list[str],
) -> dict:
    """
    Returns dict with ai_recommendation, quick_wins, red_flags.
    Returns empty dict if OPENROUTER_API_KEY is missing or the call fails.
    """
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        return {}

    news_context = ""
    if news_titles:
        news_context = "\nTitulares de prensa recientes:\n" + "\n".join(f"- {t}" for t in news_titles[:3])

    prompt = (
        f"Sos un analista experto del ecosistema emprendedor paraguayo con conocimiento "
        f"profundo del DNIT, DNCP, MIC y el mercado local.\n\n"
        f"Analizá esta idea de startup:\n"
        f"Idea: {idea}\n"
        f"Keywords del sector: {', '.join(keywords)}\n"
        f"Señal de mercado: {score}/100 ({label})\n"
        f"Empresas registradas en DNIT (TuRuc): {turuc_count}\n"
        f"Contratos DNCP (compras del Estado): {dncp_count}"
        f"{news_context}"
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
                        "Sé específico y concreto — evitá consejos genéricos."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_retries=2,
        )
        return result.model_dump()
    except Exception:
        return {}

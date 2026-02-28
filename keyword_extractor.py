import re

STOPWORDS_ES = {
    # Verbos y conectores
    "quiero", "hacer", "para", "que", "con", "los", "las", "del", "de",
    "en", "el", "la", "por", "como", "donde", "hay", "ver", "usar",
    "crear", "construir", "desarrollar", "tipo", "esto", "este", "esta",
    # Tech genérico (no aporta info de mercado)
    "app", "aplicacion", "aplicación", "sistema", "plataforma", "herramienta",
    "servicio", "producto", "web", "online", "digital", "nuevo", "nueva",
    # Negocios muy genéricos (aparecen en miles de empresas sin relación)
    "gestion", "gestión", "ideas", "idea", "proyecto", "startup", "startups",
    "solucion", "solución", "empresa", "empresas", "negocio", "negocios",
    # Palabras vacías de contexto
    "validar", "mejorar", "optimizar", "automatizar", "conectar",
    "paraguayo", "paraguaya", "paraguayos", "paraguay",
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

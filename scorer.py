from models import ScanResult


def calculate_market_signal(scan_results: list[ScanResult]) -> tuple[int, str, str]:
    """
    Returns (score: int 0-100, label: str, recommendation: str)

    Positive signal weights (normalized to available sources):
    - TuRuc (business density): 65 pts — primary saturation signal
    - MIC (local startup competition): 20 pts — direct competition
    - Google News (press coverage): 15 pts — market awareness

    Negative discount:
    - DNCP (state demand): -20 pts — opportunity/demand validation signal

    The score is normalized against the max possible from available sources,
    so quick mode (TuRuc + News only) still produces scores across 0-100.
    """
    POSITIVE_WEIGHTS = {"TuRuc": 65, "MIC": 20, "Google News PY": 15}
    DNCP_DISCOUNT = 20

    scores_by_source = {r.source: r.raw_signal for r in scan_results if r.available}

    available_max = sum(w for src, w in POSITIVE_WEIGHTS.items() if src in scores_by_source)
    if available_max == 0:
        return 0, "espacio abierto", (
            "No fue posible consultar las fuentes de datos. "
            "Intentá de nuevo o verificá la conexión a internet."
        )

    raw_positive = sum(
        scores_by_source.get(src, 0.0) * w
        for src, w in POSITIVE_WEIGHTS.items()
    )
    dncp_discount = scores_by_source.get("DNCP", 0.0) * DNCP_DISCOUNT  # already negative

    # Normalize positive score to 0-100 relative to what's available,
    # then apply DNCP discount (also normalized)
    normalized = (raw_positive / available_max) * 100 + (dncp_discount / available_max) * 100
    score = max(0, min(100, int(normalized)))

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


def generate_analysis(
    scan_results: list[ScanResult],
    score: int,
) -> tuple[list[str], list[str], list[str], list[str]]:
    """
    Returns (strengths, weaknesses, action_items, pivot_suggestions)
    based on what each scanner found.
    """
    by_source = {r.source: r for r in scan_results if r.available}
    turuc = by_source.get("TuRuc")
    dncp  = by_source.get("DNCP")
    mic   = by_source.get("MIC")
    news  = by_source.get("Google News PY")

    strengths: list[str] = []
    weaknesses: list[str] = []

    # --- TuRuc (threshold 80 = saturated) ---
    if turuc:
        if turuc.count == 0:
            strengths.append("Ninguna empresa registrada en el DNIT para este sector — mercado virgen")
        elif turuc.count < 30:
            strengths.append(f"Solo {turuc.count} negocios en DNIT — mercado poco explotado localmente")
        elif turuc.count < 80:
            strengths.append(f"{turuc.count} empresas en DNIT — sector existente con espacio para nuevos jugadores")
        else:
            weaknesses.append(f"{turuc.count} empresas ya registradas en DNIT — alta competencia establecida")

    # --- DNCP ---
    if dncp:
        if dncp.count > 50:
            strengths.append(f"El Estado tiene {dncp.count} contratos DNCP en este sector — demanda pública masiva confirmada")
        elif dncp.count > 10:
            strengths.append(f"Demanda estatal detectada ({dncp.count} contratos DNCP) — el Estado es un cliente potencial")
        elif dncp.count > 0:
            strengths.append(f"{dncp.count} contratos DNCP — sector en radar del gobierno paraguayo")

    # --- MIC ---
    if mic:
        if mic.count == 0:
            strengths.append("Sin startups en el Portal Emprendedor MIC — primera mover advantage disponible")
        elif mic.count <= 3:
            strengths.append(f"Solo {mic.count} startup(s) en MIC — poca competencia en etapa temprana")
        else:
            weaknesses.append(f"{mic.count} startups registradas en MIC ya compiten en este segmento")

    # --- Google News ---
    if news:
        if news.count == 0:
            strengths.append("Sin cobertura de prensa local — oportunidad de construir la narrativa de mercado desde cero")
        elif news.count <= 5:
            strengths.append("Poca cobertura mediática — sector no sobre-analizado, fácil diferenciarse")
        elif news.count <= 15:
            strengths.append(f"{news.count} artículos recientes — sector con interés mediático pero no saturado")
        else:
            weaknesses.append(f"{news.count} artículos de prensa recientes — sector muy visible, expectativas altas del mercado")

    # --- Score-based weaknesses ---
    if score > 70:
        weaknesses.append("Diferenciación difícil sin un ángulo muy específico y defensible")
        weaknesses.append("Riesgo de guerra de precios con jugadores ya establecidos")
    elif score > 50:
        weaknesses.append("Necesitás un nicho claro para no perderte en el ruido del mercado")

    if not turuc or not turuc.available:
        weaknesses.append("No se pudo consultar DNIT/TuRuc — datos de competencia incompletos")

    # --- Action items ---
    if score > 70:
        action_items = [
            "Entrevistá a 10 clientes del sector y encontrá su mayor frustración con los actuales proveedores",
            "Elegí un departamento del interior como mercado inicial (Alto Paraná, Itapúa o Concepción tienen menos competencia)",
            "Definí el segmento ultra-específico antes de escribir código: cooperativas, agro, pymes < 10 empleados",
            "Buscá el player dominante del sector y mapeá qué NO hace bien — eso es tu punto de entrada",
        ]
    elif score > 30:
        action_items = [
            "Mapeá exactamente qué nicho no cubren bien los competidores que encontramos",
            "Si hay demanda DNCP, contactá la oficina de DNCP para entender cómo proveer al Estado",
            "Armá un MVP enfocado exclusivamente en el segmento paraguayo, no en el mercado regional",
            "Buscá 3 clientes piloto dispuestos a pagar antes de construir la versión completa",
        ]
    else:
        action_items = [
            "Validá con 5 potenciales clientes que el problema es real y urgente para ellos",
            "Registrá tu emprendimiento en el Portal MIC para acceder a programas de apoyo del gobierno",
            "Presentate a Startup Paraguay o CONACYT — mercado abierto es argumento fuerte para fondos",
            "Construí un MVP en 2 semanas y conseguí los primeros 3 clientes pagos antes de escalar",
        ]

    # --- Pivot suggestions ---
    pivot_suggestions: list[str] = []
    if score > 50:
        pivot_suggestions = [
            "Geográfico: Ciudad del Este, Encarnación o Concepción tienen 60-80% menos competencia que Asunción",
            "Segmento: Cooperativas agropecuarias (400+ en Paraguay, poco digitalizadas y con poder adquisitivo)",
            "Modelo: B2B en vez de B2C — vender a empresas tiene menor costo de adquisición en Paraguay",
            "Vertical: Especializate en un sector concreto (ganadería, soja, turismo del Chaco, exportaciones)",
        ]
    elif score > 20:
        pivot_suggestions = [
            "Explorá expansión regional (Bolivia, norte de Argentina) una vez que tengas tracción local",
            "El segmento pymes < 10 empleados es el 90% del tejido empresarial paraguayo y está sub-atendido",
        ]

    return strengths, weaknesses, action_items, pivot_suggestions

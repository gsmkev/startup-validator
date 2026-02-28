from __future__ import annotations

import logging

from models import ScanResult, ScannerAnalysis

logger = logging.getLogger("validator.scorer")


def calculate_market_signal(scan_results: list[ScanResult]) -> tuple[int, str, str]:
    """
    Returns (score 0-100, label, recommendation).

    Weights and signal direction are read from the scanner registry so adding
    a new scanner automatically updates the formula.
    """
    from scanners import get_registry
    registry = get_registry()

    available = {r.source: r for r in scan_results if r.available}
    if not available:
        logger.warning("calculate_market_signal: no available scanners")
        return 0, "espacio abierto", (
            "No fue posible consultar las fuentes de datos. "
            "Intentá de nuevo o verificá la conexión a internet."
        )

    # Normalize over effective weights: only scanners that contributed data
    # (count > 0 or raw_signal != 0) to avoid inflating/deflating when
    # some scanners return empty while others have real signals
    effective_positive_max = 0.0
    raw_positive = 0.0
    raw_negative = 0.0

    for source, result in available.items():
        meta = registry.get(source)
        if meta is None:
            continue
        w = meta.weight
        has_data = result.count > 0 or result.raw_signal != 0.0

        if meta.signal_direction == "negative":
            if has_data:
                raw_negative += result.raw_signal * w
        else:
            raw_positive += result.raw_signal * w
            if has_data:
                effective_positive_max += w

    # Fallback: use all positive weights if no positive scanner returned data
    if effective_positive_max == 0:
        for source, result in available.items():
            meta = registry.get(source)
            if meta and meta.signal_direction == "positive":
                effective_positive_max += meta.weight

    if effective_positive_max == 0:
        return 0, "espacio abierto", "Sin fuentes positivas disponibles."

    normalized = (raw_positive / effective_positive_max) * 100 + (raw_negative / effective_positive_max) * 100
    score = max(0, min(100, int(normalized)))
    logger.debug("calculate_market_signal: raw_positive=%.2f raw_negative=%.2f effective_max=%.0f score=%d", raw_positive, raw_negative, effective_positive_max, score)

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
    Delegates to each scanner's analyze() method for source-specific insights,
    then adds score-based generic action items and pivots.
    """
    from scanners import get_registry
    registry = get_registry()

    strengths: list[str] = []
    weaknesses: list[str] = []
    action_items: list[str] = []
    pivot_suggestions: list[str] = []

    by_source = {r.source: r for r in scan_results if r.available}

    for r in scan_results:
        scanner_cls = registry.get(r.source)
        if scanner_cls is None:
            continue
        analysis: ScannerAnalysis = scanner_cls.analyze(r, score)
        strengths.extend(analysis.strengths)
        weaknesses.extend(analysis.weaknesses)
        action_items.extend(analysis.action_items)
        pivot_suggestions.extend(analysis.pivot_suggestions)

    # Cross-reference web vs registry data for deeper insights
    web = by_source.get("Web PY")
    turuc = by_source.get("TuRuc")
    if web and turuc:
        if web.count > 5 and turuc.count == 0:
            weaknesses.append(
                "Se encontraron competidores en la web pero ninguno registrado en DNIT "
                "— posible mercado informal o jugadores internacionales sin presencia fiscal en Paraguay"
            )
        elif web.count == 0 and turuc.count > 30:
            strengths.append(
                "Muchas empresas registradas pero ninguna con presencia web visible "
                "— oportunidad enorme de capturar el canal digital"
            )
            action_items.append(
                "Invertí en SEO y presencia digital desde el día 1: tus competidores formales no están online"
            )

    # Score-based generic weaknesses
    if score > 70:
        weaknesses.append("Diferenciación difícil sin un ángulo muy específico y defensible")
        weaknesses.append("Riesgo de guerra de precios con jugadores ya establecidos")
    elif score > 50:
        weaknesses.append("Necesitás un nicho claro para no perderte en el ruido del mercado")

    # Score-based action items
    if score > 70:
        action_items.extend([
            "Entrevistá a 10 clientes del sector y encontrá su mayor frustración con los actuales proveedores",
            "Elegí un departamento del interior como mercado inicial (Alto Paraná, Itapúa o Concepción tienen menos competencia)",
            "Definí el segmento ultra-específico antes de escribir código: cooperativas, agro, pymes < 10 empleados",
            "Buscá el player dominante del sector y mapeá qué NO hace bien — eso es tu punto de entrada",
        ])
    elif score > 30:
        action_items.extend([
            "Mapeá exactamente qué nicho no cubren bien los competidores que encontramos",
            "Armá un MVP enfocado exclusivamente en el segmento paraguayo, no en el mercado regional",
            "Buscá 3 clientes piloto dispuestos a pagar antes de construir la versión completa",
        ])
    else:
        action_items.extend([
            "Validá con 5 potenciales clientes que el problema es real y urgente para ellos",
            "Registrá tu emprendimiento en el Portal MIC para acceder a programas de apoyo del gobierno",
            "Presentate a Startup Paraguay o CONACYT — mercado abierto es argumento fuerte para fondos",
            "Construí un MVP en 2 semanas y conseguí los primeros 3 clientes pagos antes de escalar",
        ])

    # Pivot suggestions
    if score > 50:
        pivot_suggestions.extend([
            "Geográfico: Ciudad del Este, Encarnación o Concepción tienen 60-80% menos competencia que Asunción",
            "Segmento: Cooperativas agropecuarias (400+ en Paraguay, poco digitalizadas y con poder adquisitivo)",
            "Modelo: B2B en vez de B2C — vender a empresas tiene menor costo de adquisición en Paraguay",
            "Vertical: Especializate en un sector concreto (ganadería, soja, turismo del Chaco, exportaciones)",
        ])
    elif score > 20:
        pivot_suggestions.extend([
            "Explorá expansión regional (Bolivia, norte de Argentina) una vez que tengas tracción local",
            "El segmento pymes < 10 empleados es el 90% del tejido empresarial paraguayo y está sub-atendido",
        ])

    return strengths, weaknesses, action_items, pivot_suggestions

from __future__ import annotations
from models import ScanResult, ScannerAnalysis


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
        return 0, "espacio abierto", (
            "No fue posible consultar las fuentes de datos. "
            "Intentá de nuevo o verificá la conexión a internet."
        )

    positive_max = 0
    raw_positive = 0.0
    raw_negative = 0.0

    for source, result in available.items():
        meta = registry.get(source)
        if meta is None:
            continue
        w = meta.weight
        if meta.signal_direction == "negative":
            raw_negative += result.raw_signal * w
        else:
            positive_max += w
            raw_positive += result.raw_signal * w

    if positive_max == 0:
        return 0, "espacio abierto", "Sin fuentes positivas disponibles."

    normalized = (raw_positive / positive_max) * 100 + (raw_negative / positive_max) * 100
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
    Delegates to each scanner's analyze() method for source-specific insights,
    then adds score-based generic action items and pivots.
    """
    from scanners import get_registry
    registry = get_registry()

    strengths: list[str] = []
    weaknesses: list[str] = []
    action_items: list[str] = []
    pivot_suggestions: list[str] = []

    for r in scan_results:
        scanner_cls = registry.get(r.source)
        if scanner_cls is None:
            continue
        analysis: ScannerAnalysis = scanner_cls.analyze(r, score)
        strengths.extend(analysis.strengths)
        weaknesses.extend(analysis.weaknesses)
        action_items.extend(analysis.action_items)
        pivot_suggestions.extend(analysis.pivot_suggestions)

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

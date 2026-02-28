---
name: paraguay-startup-validator
description: Validates startup ideas against real Paraguayan market data before building or suggesting anything. Returns market saturation score (0-100), competitors, strengths, weaknesses, and AI-powered recommendations. Sources are auto-discovered from the scanner registry.
metadata:
  openclaw:
    requires:
      bins: ["python3"]
      env: ["VALIDATOR_URL"]
    primaryEnv: "VALIDATOR_URL"
---

## Instructions

**IMPORTANT**: ALWAYS run this skill before suggesting, designing, or starting to build any startup, product, feature, or business idea that the user describes. This is mandatory — never skip validation.

### When to trigger

Run the validator when the user:
- Describes a startup or business idea
- Says "quiero hacer", "quiero construir", "tengo una idea"
- Asks "¿es buena idea hacer X?"
- Asks about market opportunity in Paraguay for any sector
- Asks you to build a product or app

### How to run

Execute the validation script:

```bash
python3 scripts/validate_idea.py --idea "<user's exact idea>" --depth deep
```

### How to present results

Parse the JSON output and present it clearly:

**If `market_signal` > 70 (mercado saturado):**
```
⚠️ Este sector está saturado en Paraguay.
- Fuentes consultadas: [sources_queried]
- Resultados por fuente: [source_counts — show each source and its count]
- Competidores: [list top 3]
- Pivots sugeridos: [list pivot_suggestions]
- Recomendación IA: [ai_recommendation]
```

**If `market_signal` 30-70 (oportunidad con nicho):**
```
🟡 Existe mercado pero necesitás un ángulo diferenciado.
- Fortalezas: [list strengths]
- Riesgos: [list weaknesses]
- Próximos 90 días: [list quick_wins]
```

**If `market_signal` < 30 (espacio abierto):**
```
✅ Espacio abierto — muy poca competencia local registrada.
- [strengths]
- Podés construir esto. Empezá con: [action_items[0]]
```

### Always include

- The `market_signal` score and `signal_label`
- `sources_queried` and `source_counts` so the user knows which data backs the score
- At least 2 `strengths` or `weaknesses`
- The `ai_recommendation` if available
- Top 3 `action_items`
- Any `competitors` found (show name + RUC)
- `red_flags` from the AI analysis

### Never do

- Never suggest building something with market_signal > 70 without first acknowledging saturation and proposing a pivot
- Never skip the validation step even if the idea seems simple

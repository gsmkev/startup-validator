"use client";
import { useState } from "react";
import { SignalGauge } from "./SignalGauge";
import { CompetitorCard } from "./CompetitorCard";
import type { IdeaValidationResult } from "@/lib/api";

export function IdeaValidatorPanel() {
  const [idea, setIdea] = useState("");
  const [depth, setDepth] = useState<"quick" | "deep">("quick");
  const [result, setResult] = useState<IdeaValidationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleValidate() {
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ idea, depth }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Error desconocido");
      setResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al conectar con el servidor");
    } finally {
      setLoading(false);
    }
  }

  const signalColor =
    result && result.market_signal > 70
      ? "text-gray-600"
      : result && result.market_signal > 30
      ? "text-red-600"
      : "text-blue-700";

  return (
    <div className="max-w-2xl mx-auto space-y-5">
      {/* Input */}
      <div className="bg-white border border-gray-200 rounded-2xl p-5 space-y-3 shadow-sm">
        <textarea
          className="w-full border border-gray-200 rounded-xl p-4 text-base resize-none h-28 focus:ring-2 focus:ring-blue-500 focus:outline-none bg-gray-50"
          placeholder="Describí tu idea de startup en Paraguay... ej: 'App de pagos para cooperativas del interior'"
          value={idea}
          onChange={(e) => setIdea(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && e.metaKey) handleValidate();
          }}
        />
        <div className="flex gap-3 items-center">
          <select
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white"
            value={depth}
            onChange={(e) => setDepth(e.target.value as "quick" | "deep")}
          >
            <option value="quick">Quick — 2 fuentes (~2s)</option>
            <option value="deep">Deep — 4 fuentes (~5s)</option>
          </select>
          <button
            onClick={handleValidate}
            disabled={loading || !idea.trim()}
            className="flex-1 bg-blue-700 text-white rounded-xl px-6 py-2.5 font-semibold
                       disabled:opacity-40 hover:bg-blue-800 transition-colors text-sm"
          >
            {loading ? "Analizando mercado..." : "Validar Idea →"}
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-4">

          {/* Score principal */}
          <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
            <SignalGauge score={result.market_signal} label={result.signal_label} />
            <p className="text-xs text-gray-400 text-center mt-1">
              {result.scan_duration_ms}ms &middot; {result.sources_queried.join(", ")}
              {result.keywords_extracted.length > 0 && (
                <> &middot; keywords: <span className="text-gray-600">{result.keywords_extracted.join(", ")}</span></>
              )}
            </p>
          </div>

          {/* Resumen de métricas */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {Object.entries(result.source_counts).map(([source, count]) => (
              <StatCard
                key={source}
                label={source}
                value={count}
                sub="resultados"
                tone={
                  result.raw_scores[source] != null && result.raw_scores[source] > 0.7
                    ? "bad"
                    : result.raw_scores[source] != null && result.raw_scores[source] < -0.1
                    ? "good"
                    : "neutral"
                }
              />
            ))}
            <StatCard
              label="Fuentes activas"
              value={result.sources_queried.length}
              sub={`de ${result.sources_queried.length + result.sources_unavailable.length} totales`}
              tone="neutral"
            />
          </div>

          {/* Recomendación */}
          <div className={`rounded-2xl p-5 border ${
            result.market_signal > 70
              ? "bg-gray-50 border-gray-200"
              : result.market_signal > 30
              ? "bg-orange-50 border-orange-200"
              : "bg-blue-50 border-blue-200"
          }`}>
            <p className={`text-xs font-semibold uppercase tracking-wide mb-1 ${signalColor}`}>
              Diagnóstico
            </p>
            <p className="text-sm text-gray-800 leading-relaxed">{result.recommendation}</p>
          </div>

          {/* AI Analysis — OpenRouter gpt-oss-120b */}
          {(result.ai_recommendation || result.quick_wins.length > 0 || result.red_flags.length > 0) && (
            <div className="bg-indigo-50 border border-indigo-200 rounded-2xl p-5 space-y-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-indigo-600">
                Análisis IA · GPT-OSS via OpenRouter
              </p>

              {result.ai_recommendation && (
                <p className="text-sm text-indigo-900 leading-relaxed">{result.ai_recommendation}</p>
              )}

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {result.quick_wins.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-indigo-700 mb-2">Primeros 90 días</p>
                    <ol className="space-y-1.5">
                      {result.quick_wins.map((w, i) => (
                        <li key={i} className="flex gap-2 text-sm text-indigo-900">
                          <span className="shrink-0 w-5 h-5 rounded-full bg-indigo-200 text-indigo-700 font-bold text-xs flex items-center justify-center">
                            {i + 1}
                          </span>
                          <span>{w}</span>
                        </li>
                      ))}
                    </ol>
                  </div>
                )}

                {result.red_flags.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-red-600 mb-2">Red flags Paraguay</p>
                    <ul className="space-y-1.5">
                      {result.red_flags.map((f, i) => (
                        <li key={i} className="flex gap-2 text-sm text-red-800">
                          <span className="shrink-0 text-red-400 mt-0.5">!</span>
                          <span>{f}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Fortalezas y Debilidades */}
          {(result.strengths.length > 0 || result.weaknesses.length > 0) && (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {result.strengths.length > 0 && (
                <div className="bg-green-50 border border-green-200 rounded-2xl p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-green-700 mb-3">
                    Puntos fuertes
                  </p>
                  <ul className="space-y-2">
                    {result.strengths.map((s, i) => (
                      <li key={i} className="flex gap-2 text-sm text-green-900">
                        <span className="mt-0.5 shrink-0 text-green-500">✓</span>
                        <span>{s}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {result.weaknesses.length > 0 && (
                <div className="bg-red-50 border border-red-200 rounded-2xl p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-red-700 mb-3">
                    Riesgos detectados
                  </p>
                  <ul className="space-y-2">
                    {result.weaknesses.map((w, i) => (
                      <li key={i} className="flex gap-2 text-sm text-red-900">
                        <span className="mt-0.5 shrink-0 text-red-400">✗</span>
                        <span>{w}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Próximos pasos */}
          {result.action_items.length > 0 && (
            <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-3">
                Próximos pasos concretos
              </p>
              <ol className="space-y-3">
                {result.action_items.map((item, i) => (
                  <li key={i} className="flex gap-3 text-sm text-gray-800">
                    <span className="shrink-0 w-6 h-6 rounded-full bg-blue-100 text-blue-700 font-bold text-xs flex items-center justify-center">
                      {i + 1}
                    </span>
                    <span className="leading-relaxed pt-0.5">{item}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}

          {/* Pivot suggestions */}
          {result.pivot_suggestions.length > 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded-2xl p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-amber-700 mb-3">
                Pivots sugeridos para el mercado paraguayo
              </p>
              <ul className="space-y-2">
                {result.pivot_suggestions.map((p, i) => (
                  <li key={i} className="flex gap-2 text-sm text-amber-900">
                    <span className="shrink-0 text-amber-500 mt-0.5">→</span>
                    <span>{p}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Competidores */}
          {result.competitors.length > 0 && (
            <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-3">
                Competidores locales encontrados ({result.competitors.length})
              </p>
              <div className="space-y-2">
                {result.competitors.map((c, i) => (
                  <CompetitorCard key={i} competitor={c} />
                ))}
              </div>
            </div>
          )}

          {/* Noticias recientes */}
          {result.news_samples.length > 0 && (
            <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-3">
                Cobertura de prensa reciente
              </p>
              <ul className="space-y-2">
                {result.news_samples.map((title, i) => (
                  <li key={i} className="flex gap-2 text-sm text-gray-700">
                    <span className="shrink-0 text-gray-300 mt-0.5">▸</span>
                    <span className="leading-snug">{title}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Señales de mercado */}
          {result.market_hints.length > 0 && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2 px-1">
                Señales de mercado
              </p>
              <div className="flex flex-wrap gap-2">
                {result.market_hints.map((h, i) => (
                  <span
                    key={i}
                    className={`px-3 py-1 rounded-full text-xs font-medium ${
                      h.type === "opportunity"
                        ? "bg-green-100 text-green-800"
                        : h.type === "warning"
                        ? "bg-red-100 text-red-800"
                        : "bg-gray-100 text-gray-700"
                    }`}
                  >
                    {h.hint}
                  </span>
                ))}
              </div>
            </div>
          )}

          {result.sources_unavailable.length > 0 && (
            <p className="text-xs text-gray-400 text-center">
              Fuentes no disponibles: {result.sources_unavailable.join(", ")}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function StatCard({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: number | string;
  sub: string;
  tone: "good" | "bad" | "neutral";
}) {
  const valueColor =
    tone === "good"
      ? "text-green-700"
      : tone === "bad"
      ? "text-red-600"
      : "text-gray-900";

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 text-center shadow-sm">
      <p className={`text-2xl font-bold ${valueColor}`}>{value}</p>
      <p className="text-xs font-semibold text-gray-700 mt-1">{label}</p>
      <p className="text-xs text-gray-400 mt-0.5">{sub}</p>
    </div>
  );
}

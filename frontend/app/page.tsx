"use client";
import { useState } from "react";
import { IdeaValidatorPanel } from "@/components/IdeaValidatorPanel";
import { ChatPanel } from "@/components/ChatPanel";

type Tab = "validador" | "agente";

export default function Home() {
  const [tab, setTab] = useState<Tab>("validador");

  return (
    <main className="min-h-screen py-12 px-4">
      <div className="max-w-2xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Paraguay Startup Validator
          </h1>
          <p className="text-gray-500 text-sm">
            Validá tu idea contra datos reales del DNIT, MIC y prensa paraguaya
          </p>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-gray-100 rounded-xl p-1 mb-6">
          <button
            onClick={() => setTab("validador")}
            className={`flex-1 py-2 text-sm font-semibold rounded-lg transition-colors ${
              tab === "validador"
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            Validador
          </button>
          <button
            onClick={() => setTab("agente")}
            className={`flex-1 py-2 text-sm font-semibold rounded-lg transition-colors ${
              tab === "agente"
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            Agente IA
            <span className="ml-1.5 text-xs px-1.5 py-0.5 rounded-full bg-indigo-100 text-indigo-600">
              OpenClaw
            </span>
          </button>
        </div>

        {tab === "validador" ? <IdeaValidatorPanel /> : <ChatPanel />}
      </div>
    </main>
  );
}

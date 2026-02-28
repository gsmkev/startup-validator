import { NextRequest, NextResponse } from "next/server";

const REST_BRIDGE_URL = process.env.REST_BRIDGE_URL ?? "http://localhost:8001";

export async function POST(req: NextRequest) {
  const body = await req.json();

  let res: Response;
  try {
    res = await fetch(`${REST_BRIDGE_URL}/agent`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    return NextResponse.json(
      { role: "assistant", content: "⚠️ No se pudo conectar al backend. Asegurate de que esté corriendo: `uvicorn rest_bridge:app --port 8001`" },
      { status: 502 }
    );
  }

  let data: unknown;
  try {
    data = await res.json();
  } catch {
    return NextResponse.json(
      { role: "assistant", content: "⚠️ El backend devolvió una respuesta inválida. Revisá los logs del servidor." },
      { status: 500 }
    );
  }
  return NextResponse.json(data, { status: res.ok ? 200 : res.status });
}

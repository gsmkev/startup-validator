import { NextRequest, NextResponse } from "next/server";

const REST_BRIDGE_URL = process.env.REST_BRIDGE_URL ?? "http://localhost:8001";

export async function POST(req: NextRequest) {
  const body = await req.json();

  let res: Response;
  try {
    res = await fetch(`${REST_BRIDGE_URL}/validate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    return NextResponse.json(
      { error: `No se pudo conectar al backend en ${REST_BRIDGE_URL}. Corré: uv run uvicorn rest_bridge:app --port 8001` },
      { status: 502 }
    );
  }

  if (!res.ok) {
    return NextResponse.json({ error: "Backend error" }, { status: 502 });
  }

  return NextResponse.json(await res.json());
}

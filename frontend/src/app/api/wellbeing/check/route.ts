import { NextRequest, NextResponse } from "next/server";
const PY_BACKEND_URL = process.env.PY_BACKEND_URL || "http://localhost:8000";

export async function POST(req: NextRequest) {
  const body = await req.json();
  const r = await fetch(`${PY_BACKEND_URL}/wellbeing/check`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await r.json();
  return NextResponse.json(data, { status: r.ok ? 200 : 500 });
}

import { NextRequest, NextResponse } from "next/server";

const PY_BACKEND_URL = process.env.PY_BACKEND_URL || "http://localhost:8000";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    // Expected: { course_context, week_context, question, history }
    const resp = await fetch(`${PY_BACKEND_URL}/lesson_chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!resp.ok) {
      const txt = await resp.text();
      return NextResponse.json(
        { error: `Backend error: ${resp.status} ${txt}` },
        { status: 500 }
      );
    }

    const data = await resp.json();
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json(
      { error: e?.message || "Unknown error" },
      { status: 500 }
    );
  }
}

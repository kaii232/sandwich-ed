import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const backend = process.env.BACKEND_URL || "http://localhost:8000";
    const r = await fetch(`${backend}/study_tips`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!r.ok) {
      const text = await r.text();
      return NextResponse.json(
        { error: "backend_error", detail: text },
        { status: 502 }
      );
    }

    const tips = await r.json();
    // Expected to be a List[str]
    return NextResponse.json(tips);
  } catch (e: any) {
    return NextResponse.json(
      { error: "proxy_error", detail: e?.message ?? String(e) },
      { status: 500 }
    );
  }
}

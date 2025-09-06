import { NextRequest } from "next/server";

export async function POST(req: NextRequest) {
  const body = await req.json(); // expects { lesson_info, course_context }
  const backend = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

  const res = await fetch(`${backend}/get_lesson_content`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const data = await res.json();
  return new Response(JSON.stringify(data), {
    status: res.status,
    headers: { "Content-Type": "application/json" },
  });
}

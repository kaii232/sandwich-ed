export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type ChatState = Record<string, any>;
export type ChatResp = {
  state: ChatState;
  bot: string;
  syllabus?: string;
  course_ready?: boolean;
  error?: string;
};

export async function chatbotStep(
  state: ChatState,
  user_input?: string
): Promise<ChatResp> {
  const res = await fetch(`${API_BASE}/chatbot_step`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ state, user_input }),
  });
  if (!res.ok) throw new Error(`chatbot_step failed: ${res.status}`);
  return res.json();
}

export async function initializeCourse(
  syllabus_text: string,
  course_context: any
) {
  const res = await fetch(`${API_BASE}/initialize_course`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ syllabus_text, course_context }),
  });
  if (!res.ok) throw new Error(`initialize_course failed: ${res.status}`);
  return res.json();
}

export async function getLessonContent(lesson_info: any, course_context: any) {
  const res = await fetch(`${API_BASE}/get_lesson_content`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lesson_info, course_context }),
  });
  if (!res.ok) throw new Error(`get_lesson_content failed: ${res.status}`);
  return res.json(); // -> { success, lesson_content }
}

export async function getWeekContent(week_number: number, course_data: any) {
  const res = await fetch(`${API_BASE}/get_week_content`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ week_number, course_data }),
  });
  if (!res.ok) throw new Error(`get_week_content failed: ${res.status}`);
  return res.json();
}

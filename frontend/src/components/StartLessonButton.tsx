"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { initializeCourse, getWeekContent } from "@/lib/api";

type Props = {
  syllabus?: string; // optional: markdown syllabus from chatbot
  chatState?: {
    topic?: string;
    difficulty?: string;
    duration?: string; // e.g. "6 weeks" or "1 month"
    learner_type?: string;
  };
};

export default function StartLessonButton({ syllabus, chatState }: Props) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  function buildFallbackSyllabus(topic: string, totalWeeks: number) {
    // a minimal, parseable markdown syllabus (Week headings + a few bullets)
    const weeks = Array.from({ length: totalWeeks }).map((_, i) => {
      const n = i + 1;
      const title =
        n === 1 ? "Introduction" : n === 2 ? "Core Concepts" : `Module ${n}`;
      return `# Week ${n}: ${title}
- Overview of ${topic}
- Key ideas & examples
- Practice exercise
`;
    });
    return `# ${topic} — Auto Syllabus\n\n${weeks.join("\n")}`.trim();
  }

  function parseWeeks(duration: string | undefined) {
    if (!duration) return 8; // default
    // very light parsing; you can enhance later
    const m = duration.match(/(\d+)\s*(week|weeks|wk)/i);
    if (m) return Math.max(1, parseInt(m[1], 10));
    const m2 = duration.match(/(\d+)\s*(month|months|mo)/i);
    if (m2) return Math.max(4, parseInt(m2[1], 10) * 4);
    return 8;
  }

  async function handleStart() {
    if (loading) return;
    setLoading(true);
    try {
      const topic = (chatState?.topic || "Machine Learning").trim();
      const duration = (chatState?.duration || "6 weeks").trim();
      const totalWeeks = parseWeeks(duration);

      const syllabusText =
        syllabus && syllabus.trim().length > 0
          ? syllabus.trim()
          : buildFallbackSyllabus(topic, totalWeeks);

      const course_context = {
        topic,
        difficulty: (chatState?.difficulty || "beginner").toLowerCase(),
        duration,
        learner_type: chatState?.learner_type || "Mix of all approaches",
      };

      // 1) Initialize course on backend
      const init = await initializeCourse(syllabusText, course_context);
      const course_data = init.course_data; // contains { weeks, navigation, summary, ... }

      // 2) Prefetch Week 1 content
      const wk1 = await getWeekContent(1, course_data);

      // 3) Persist for the /lesson page
      sessionStorage.setItem("courseData", JSON.stringify(course_data));
      sessionStorage.setItem("currentWeek", JSON.stringify(1));
      sessionStorage.setItem(
        "weekContent:1",
        JSON.stringify(wk1.week_content || null)
      );

      // 4) go to lesson page
      router.push("/lesson");
    } catch (e: any) {
      console.error(e);
      alert(
        `Could not start lesson.\n` +
          `• Is the backend running at ${
            process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000"
          }?\n` +
          `• Check the server logs for /initialize_course and /get_week_content.`
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <button
      onClick={handleStart}
      disabled={loading}
      aria-busy={loading}
      className="px-4 py-2 rounded-lg border text-white disabled:opacity-60"
      title="Generate your first lesson"
    >
      {loading ? "Starting…" : "Start Lesson"}
    </button>
  );
}

//Home

"use client";

import { useState, useEffect } from "react";
import ChatPanel from "@/components/ChatPanel";
import { useRouter } from "next/navigation";
import { initializeCourse, getWeekContent } from "@/lib/api";

// If you didn't make a separate StartLessonCTA yet, this inline CTA is enough.
function StartLessonCTA({
  syllabus,
  chatState,
}: {
  syllabus?: string;
  chatState?: any;
}) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  async function handleStart() {
    setLoading(true);
    try {
      // Clear previous session data when starting new lesson
      sessionStorage.removeItem("sessionQuizResults");
      sessionStorage.removeItem("currentSessionActive");
      sessionStorage.removeItem("completedLessons");

      // Clear individual quiz results
      for (let i = 1; i <= 20; i++) {
        sessionStorage.removeItem(`sessionQuizResult:week${i}`);
      }

      const syllabusText = syllabus?.trim();

      // 1) initialize course
      const init = await initializeCourse(syllabusText ?? "", chatState ?? {});

      // 2) prefetch week 1
      const wk1 = await getWeekContent(1, init.course_data);

      // 3) persist minimal state for the /lesson page
      sessionStorage.setItem("courseData", JSON.stringify(init.course_data));
      sessionStorage.setItem("currentWeek", JSON.stringify(1));
      sessionStorage.setItem(
        "weekContent:1",
        JSON.stringify(wk1.week_content ?? null)
      );

      // 4) Mark session as active
      sessionStorage.setItem("currentSessionActive", "true");

      // 5) navigate
      router.push("/lesson");
    } catch (e) {
      console.error(e);
      alert(
        "Could not start lesson. Is the backend running on http://localhost:8000 ?"
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <button
      onClick={handleStart}
      disabled={loading}
      className="px-4 py-2 rounded-lg bg-green-600 text-white disabled:opacity-60"
    >
      {loading ? "Starting…" : "Start Lesson"}
    </button>
  );
}

export default function Page() {
  const [chatState, setChatState] = useState<any>({});
  const [syllabus, setSyllabus] = useState<string>("");

  // Clear previous session data when page loads (new conversation)
  useEffect(() => {
    // Clear quiz results and session data on page load
    sessionStorage.removeItem("sessionQuizResults");
    sessionStorage.removeItem("currentSessionActive");
    sessionStorage.removeItem("completedLessons");

    // Clear individual quiz results
    for (let i = 1; i <= 20; i++) {
      sessionStorage.removeItem(`sessionQuizResult:week${i}`);
    }

    // Clear any existing course data from previous sessions
    sessionStorage.removeItem("courseData");
    sessionStorage.removeItem("currentWeek");

    // Clear cached week content
    for (let i = 1; i <= 20; i++) {
      sessionStorage.removeItem(`weekContent:${i}`);
    }
  }, []); // Empty dependency array means this runs once when component mounts

  return (
    <main className="max-w-4xl mx-auto p-6 space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold">AI Course Tutor</h1>
        <p className="text-sm text-gray-600">
          Tell the tutor what you want to learn → get a syllabus → click{" "}
          <b>Start Lesson</b>.
        </p>
      </header>

      {/* 1) Chatbot */}
      <section>
        <ChatPanel
          onState={setChatState}
          onSyllabus={(md, st) => {
            setSyllabus(md);
            setChatState(st);
          }}
        />
      </section>

      {/* 3) Always-visible CTA so you can proceed even if chat didn't produce a syllabus yet */}
      <section className="flex items-center gap-3">
        <span className="text-sm text-gray-500">
          Complete the chat (topic, level, duration, style) or generate a
          syllabus to enable <b>Start Lesson</b>.
        </span>
      </section>

      {/* 4) tiny status row for debugging */}
      <section className="text-xs text-gray-500">
        <div>Has syllabus: {syllabus ? "yes" : "no"}</div>
        <div>
          Topic: {chatState?.topic ?? "—"} | Difficulty:{" "}
          {chatState?.difficulty ?? "—"}
        </div>
      </section>
    </main>
  );
}

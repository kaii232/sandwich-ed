"use client";

import { useState } from "react";
import ChatPanel from "@/components/ChatPanel";
import SyllabusViewer from "@/components/SyllabusViewer";
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
      // fallback syllabus if chat hasn't produced one yet
      const fallback = `# Machine Learning (Beginner)
- Week 1: Intro to ML, basic terminology
- Week 2: Data prep (cleaning, splitting, metrics)
- Week 3: Regression (linear, evaluation)
- Week 4: Classification (logistic, kNN)
- Week 5: Unsupervised (k-means, PCA)
- Week 6: Mini-project & recap
`;
      const syllabusText = syllabus?.trim() ? syllabus : fallback;

      const ctx = {
        topic: chatState?.topic ?? "Machine Learning",
        difficulty: chatState?.difficulty ?? "Beginner",
        duration: chatState?.duration ?? "6 weeks",
        learner_type: chatState?.learner_type ?? "General",
      };

      // 1) initialize course
      const init = await initializeCourse(syllabusText, ctx);

      // 2) prefetch week 1
      const wk1 = await getWeekContent(1, init.course_data);

      // 3) persist minimal state for the /lesson page
      sessionStorage.setItem("courseData", JSON.stringify(init.course_data));
      sessionStorage.setItem("currentWeek", JSON.stringify(1));
      sessionStorage.setItem(
        "weekContent:1",
        JSON.stringify(wk1.week_content ?? null)
      );

      // 4) navigate
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

      {/* 2) Syllabus viewer (only shows if we have one) */}
      {syllabus && (
        <section>
          <SyllabusViewer
            syllabus={syllabus}
            onStart={() => {
              /* you can keep this noop; we use the CTA below */
            }}
          />
        </section>
      )}

      {/* 3) Always-visible CTA so you can proceed even if chat didn't produce a syllabus yet */}
      <section className="flex items-center gap-3">
        <StartLessonCTA syllabus={syllabus} chatState={chatState} />
        <span className="text-xs text-gray-500">
          Works even without a syllabus — uses a safe default.
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

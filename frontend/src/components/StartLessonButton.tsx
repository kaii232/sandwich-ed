"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { initializeCourse, getWeekContent } from "@/lib/api";

type Props = {
  syllabus?: string; // if you already have one from the chatbot
  chatState?: any; // optional: topic/difficulty/etc captured during chat
};

const DEFAULT_SYLLABUS = `# Machine Learning (Beginner)
- Week 1: Intro to ML, basic terminology
- Week 2: Data prep (cleaning, splitting, metrics)
- Week 3: Regression (linear, evaluation)
- Week 4: Classification (logistic, kNN)
- Week 5: Unsupervised (k-means, PCA)
- Week 6: Mini-project & recap
`;

export default function StartLessonButton({ syllabus, chatState }: Props) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  async function handleStart() {
    setLoading(true);
    try {
      const syllabusText =
        syllabus && syllabus.trim().length > 0 ? syllabus : DEFAULT_SYLLABUS;
      const course_context = {
        topic: chatState?.topic ?? "Machine Learning",
        difficulty: chatState?.difficulty ?? "Beginner",
        duration: chatState?.duration ?? "6 weeks",
        learner_type: chatState?.learner_type ?? "General",
      };

      // 1) Initialize course on backend
      const init = await initializeCourse(syllabusText, course_context);
      // 2) Prefetch Week 1 content
      const wk1 = await getWeekContent(1, init.course_data);

      // 3) Persist minimal state for the /lesson page
      sessionStorage.setItem("courseData", JSON.stringify(init.course_data));
      sessionStorage.setItem("currentWeek", JSON.stringify(1));
      sessionStorage.setItem(
        "weekContent:1",
        JSON.stringify(wk1.week_content || null)
      );

      // 4) go to lesson page
      router.push("/lesson");
    } catch (e) {
      console.error(e);
      alert("Could not start lesson. Is the backend running on port 8000?");
    } finally {
      setLoading(false);
    }
  }

  return (
    <button
      onClick={handleStart}
      disabled={loading}
      className="px-4 py-2 rounded-lg bg-green-600 text-white disabled:opacity-60"
      title="Generate your first lesson"
    >
      {loading ? "Starting…" : "Start Lesson"}
    </button>
  );
}

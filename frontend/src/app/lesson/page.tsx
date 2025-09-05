"use client";
import { useEffect, useState } from "react";
import WeekViewer from "@/components/WeekViewer";
import { getWeekContent } from "@/lib/api";

export default function LessonPage() {
  const [courseData, setCourseData] = useState<any>(null);
  const [weekNum, setWeekNum] = useState<number>(1);
  const [week, setWeek] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  // load from sessionStorage (set by StartLessonButton)
  useEffect(() => {
    const cd = sessionStorage.getItem("courseData");
    if (!cd) return; // no initialized course
    setCourseData(JSON.parse(cd));

    const savedWeek = Number(
      JSON.parse(sessionStorage.getItem("currentWeek") || "1")
    );
    setWeekNum(savedWeek);

    const cached = sessionStorage.getItem(`weekContent:${savedWeek}`);
    if (cached) setWeek(JSON.parse(cached));
    else void fetchWeek(savedWeek, JSON.parse(cd));
  }, []);

  async function fetchWeek(targetWeek: number, cd?: any) {
    if (!courseData && !cd) return;
    setLoading(true);
    try {
      const res = await getWeekContent(targetWeek, cd ?? courseData);
      setWeek(res.week_content);
      setWeekNum(targetWeek);
      sessionStorage.setItem("currentWeek", JSON.stringify(targetWeek));
      sessionStorage.setItem(
        `weekContent:${targetWeek}`,
        JSON.stringify(res.week_content || null)
      );
    } catch (e) {
      console.error(e);
      alert("Failed to load week content.");
    } finally {
      setLoading(false);
    }
  }

  function prevWeek() {
    if (weekNum <= 1) return;
    fetchWeek(weekNum - 1);
  }
  function nextWeek() {
    fetchWeek(weekNum + 1);
  }

  if (!courseData) {
    return (
      <main className="max-w-4xl mx-auto p-6 space-y-4">
        <h1 className="text-xl font-semibold">No course yet</h1>
        <p>
          Go back to the home page and click <b>Start Lesson</b> to initialize
          your course.
        </p>
      </main>
    );
  }

  return (
    <main className="max-w-4xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Lesson — Week {weekNum}</h1>
        <div className="flex gap-2">
          <button
            onClick={prevWeek}
            disabled={loading || weekNum <= 1}
            className="px-3 py-2 rounded-lg border disabled:opacity-60"
          >
            ← Previous
          </button>
          <button
            onClick={nextWeek}
            disabled={loading}
            className="px-3 py-2 rounded-lg border disabled:opacity-60"
          >
            Next →
          </button>
        </div>
      </div>

      {loading && (
        <div className="text-sm text-gray-500">Loading week content…</div>
      )}
      <WeekViewer week={week} />
    </main>
  );
}

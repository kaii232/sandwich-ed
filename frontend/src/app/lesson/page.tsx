"use client";
import { useEffect, useMemo, useState } from "react";
import { getWeekContent } from "@/lib/api";
import WeekViewer from "@/components/WeekViewer";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";

export default function LessonPage() {
  const [courseData, setCourseData] = useState<any>(null);
  const [weekNum, setWeekNum] = useState<number>(1);
  const [week, setWeek] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const cd = sessionStorage.getItem("courseData");
    if (!cd) return; // no initialized course yet

    const parsed = JSON.parse(cd);
    setCourseData(parsed);

    const savedWeek = Number(
      JSON.parse(sessionStorage.getItem("currentWeek") || "1")
    );
    setWeekNum(savedWeek);

    const cached = sessionStorage.getItem(`weekContent:${savedWeek}`);
    if (cached) setWeek(JSON.parse(cached));
    else void fetchWeek(savedWeek, parsed);
  }, []);

  async function fetchWeek(targetWeek: number, cd?: any) {
    if (!courseData && !cd) return;
    setLoading(true);
    setError(null);
    try {
      const res = await getWeekContent(targetWeek, cd ?? courseData);
      setWeek(res.week_content);
      setWeekNum(targetWeek);
      sessionStorage.setItem("currentWeek", JSON.stringify(targetWeek));
      sessionStorage.setItem(
        `weekContent:${targetWeek}`,
        JSON.stringify(res.week_content || null)
      );
    } catch (e: any) {
      setError(e?.message || "Failed to load week content.");
    } finally {
      setLoading(false);
    }
  }

  function prevWeek() {
    if (weekNum > 1) fetchWeek(weekNum - 1);
  }
  function nextWeek() {
    fetchWeek(weekNum + 1);
  }

  // ✅ Hooks/derived values must be called unconditionally:
  const totalWeeks = courseData?.total_weeks;
  const progressPct = useMemo(
    () => Math.min(100, Math.max(0, ((weekNum - 1) / totalWeeks) * 100)),
    [weekNum, totalWeeks]
  );

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
    <main className="max-w-7xl mx-auto p-4 md:p-6 grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-4">
      {/* Sidebar */}
      <aside className="lg:sticky lg:top-6 h-fit">
        <Card className="rounded-2xl">
          <CardHeader>
            <div className="flex items-start justify-between gap-2">
              <div>
                <CardTitle className="text-xl">
                  {courseData.title || "Your Course"}
                </CardTitle>
                <p className="text-sm text-neutral-600 mt-1 line-clamp-3">
                  {courseData.description ||
                    "Personalized learning path powered by your Agentic AI."}
                </p>
              </div>
              <Badge>Week {weekNum}</Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <div className="flex items-center justify-between text-sm mb-2">
                <span>Progress</span>
                <span className="text-neutral-600">
                  {Math.round(progressPct)}%
                </span>
              </div>
              <Progress value={progressPct} />
              <div className="mt-2 text-xs text-neutral-600">
                {weekNum - 1} of {totalWeeks} completed
              </div>
            </div>

            <div className="border-t pt-4 space-y-3">
              <div className="text-xs uppercase tracking-wide text-neutral-500">
                Weeks
              </div>
              <div className="grid grid-cols-3 gap-2 max-h-64 overflow-auto pr-1">
                {Array.from({ length: totalWeeks }).map((_, idx) => {
                  const n = idx + 1;
                  const isDone = n < weekNum;
                  const isCurrent = n === weekNum;
                  return (
                    <button
                      key={n}
                      onClick={() => fetchWeek(n)}
                      className={`relative aspect-[3/2] rounded-xl border text-xs flex items-center justify-center transition ${
                        isCurrent
                          ? "border-neutral-900 ring-2 ring-neutral-300"
                          : isDone
                          ? "border-neutral-200 bg-neutral-100"
                          : "hover:bg-neutral-100"
                      }`}
                    >
                      <span className="font-medium">W{n}</span>
                      {isDone && (
                        <span className="absolute right-1.5 top-1.5 h-2.5 w-2.5 rounded-full bg-emerald-500" />
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          </CardContent>
        </Card>
      </aside>

      {/* Main */}
      <section className="space-y-4">
        {/* Header bar */}
        <div className="rounded-2xl border bg-white p-3 sm:p-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-2xl font-semibold">Lesson — Week {weekNum}</h1>
            <p className="text-sm text-neutral-600">
              Continue your personalized curriculum
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="hidden md:block">
              <select
                className="w-[160px] rounded-xl border px-3 py-2 text-sm"
                value={String(weekNum)}
                onChange={(e) => fetchWeek(Number(e.target.value))}
              >
                {Array.from({ length: totalWeeks }).map((_, i) => (
                  <option key={i} value={String(i + 1)}>
                    Week {i + 1}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex gap-2">
              <Button
                onClick={prevWeek}
                disabled={loading || weekNum <= 1}
                variant="outline"
              >
                ← Previous
              </Button>
              <Button onClick={nextWeek} disabled={loading}>
                Next →
              </Button>
            </div>
          </div>
        </div>

        {/* Utility bar */}
        <div className="flex flex-col sm:flex-row gap-2 sm:items-center sm:justify-between">
          <div className="relative w-full sm:w-[320px]">
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-neutral-500">
              🔎
            </span>
            <Input
              className="pl-8"
              placeholder="Search within this week (headings, tasks)…"
            />
          </div>
          <div className="text-sm text-neutral-600">
            Week {weekNum} of {totalWeeks}
          </div>
        </div>

        {/* Content surface */}
        <Card className="rounded-2xl">
          <CardContent className="p-4 sm:p-6">
            {error && (
              <div className="mb-4 rounded-xl border border-red-300 bg-red-50 p-3 text-sm">
                {error}
              </div>
            )}
            {loading && (
              <div className="space-y-3 animate-pulse">
                <div className="h-4 w-1/2 bg-neutral-200 rounded" />
                <div className="h-3 w-2/3 bg-neutral-200 rounded" />
                <div className="h-3 w-2/5 bg-neutral-200 rounded" />
                <div className="h-48 w-full bg-neutral-200 rounded-xl" />
              </div>
            )}
            {!loading && (
              <WeekViewer
                week={week}
                onLoadLesson={async (lessonInfo) => {
                  // Optional: lazy-load lesson details from backend
                  try {
                    const res = await fetch("/api/lesson", {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({
                        lesson_info: lessonInfo,
                        course_context: courseData,
                      }),
                    });
                    const data = await res.json();
                    return data.lesson; // {content, videos, ...}
                  } catch (e) {
                    console.error(e);
                    return null;
                  }
                }}
              />
            )}
          </CardContent>
        </Card>
      </section>
    </main>
  );
}

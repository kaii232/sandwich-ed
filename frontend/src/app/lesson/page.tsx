"use client";
import { useEffect, useMemo, useState, useRef } from "react";
import { getWeekContent } from "@/lib/api";
import WeekViewer from "@/components/WeekViewer";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import LessonChatbot from "@/components/LessonChatbot";
import SideTaskbar from "@/components/SideTaskbar";
import StudyTipsLoader from "@/components/StudyTipsLoader";

interface LessonTopic {
  id: string;
  title: string;
  summary: string;
  expandable: boolean;
  loaded: boolean;
  completed?: boolean;
}

interface WeekData {
  week_number: number;
  title: string;
  overview?: string;
  lesson_topics?: LessonTopic[];
  activities?: string;
  completed: boolean;
  progress: number;
}

export default function LessonPage() {
  const [courseData, setCourseData] = useState<any>(null);
  const [weekNum, setWeekNum] = useState<number>(1);
  const [week, setWeek] = useState<WeekData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedWeeks, setExpandedWeeks] = useState<Set<number>>(new Set([1]));
  const [expandedLessons, setExpandedLessons] = useState<Set<string>>(
    new Set()
  );
  const [completedLessons, setCompletedLessons] = useState<Set<string>>(
    new Set()
  );
  const [activeSection, setActiveSection] = useState<string>("overview");
  const [savedQuizResults, setSavedQuizResults] = useState<Record<string, any>>(
    {}
  );

  useEffect(() => {
    const cd = sessionStorage.getItem("courseData");
    if (!cd) {
      // No course data - reset everything
      setSavedQuizResults({});
      return;
    }

    const parsed = JSON.parse(cd);
    setCourseData(parsed);

    // Always check for fresh session - if no sessionQuizResults exists, it's a fresh start
    const existingResults = sessionStorage.getItem("sessionQuizResults");
    if (!existingResults) {
      // Fresh session - ensure everything is clear
      sessionStorage.removeItem("sessionQuizResults");
      sessionStorage.removeItem("allQuizResults"); // Also clear old key
      setSavedQuizResults({});
    } else {
      // Load existing session results
      const allResults = JSON.parse(existingResults || "{}");
      setSavedQuizResults(allResults);
    }

    // Mark session as active
    sessionStorage.setItem("currentSessionActive", "true");

    const savedWeek = Number(
      JSON.parse(sessionStorage.getItem("currentWeek") || "1")
    );
    setWeekNum(savedWeek);

    // Load completion data
    const completedData = sessionStorage.getItem("completedLessons");
    if (completedData) {
      setCompletedLessons(new Set(JSON.parse(completedData)));
    }

    const cached = sessionStorage.getItem(`weekContent:${savedWeek}`);
    if (cached) setWeek(JSON.parse(cached));
    else void fetchWeek(savedWeek, parsed);
  }, []);

  const [tipsOpen, setTipsOpen] = useState(false);
  const tipsCount = useRef(0);

  const openTips = () => {
    tipsCount.current += 1;
    setTipsOpen(true);
  };
  const closeTips = () => {
    tipsCount.current = Math.max(0, tipsCount.current - 1);
    if (tipsCount.current === 0) setTipsOpen(false);
  };

  const withTips = async <T,>(fn: () => Promise<T>) => {
    openTips();
    try {
      return await fn();
    } finally {
      closeTips();
    }
  };

  async function fetchWeek(targetWeek: number, cd?: any) {
    if (!courseData && !cd) return;
    setLoading(true);
    openTips();
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

      // Expand current week in sidebar
      setExpandedWeeks((prev) => new Set([...prev, targetWeek]));
    } catch (e: any) {
      setError(e?.message || "Failed to load week content.");
    } finally {
      setLoading(false);
      closeTips();
    }
  }

  const getNextIngredientPrompt = () => {
    const wk = courseData?.weeks?.find((w: any) => w.week_number === weekNum);
    if (!wk) return null;

    // What’s the next action?
    // overview -> first lesson
    if (activeSection === "overview" && wk.lesson_topics?.[0]) {
      return `Start “${wk.lesson_topics[0].title}” to earn your next ingredient 🍅`;
    }

    // lesson -> next lesson/resources/quiz
    const idx =
      wk.lesson_topics?.findIndex((ls: any) => ls.id === activeSection) ?? -1;
    if (idx >= 0 && idx < (wk.lesson_topics?.length ?? 0) - 1) {
      return `Finish “${wk.lesson_topics[idx].title}” to unlock “${
        wk.lesson_topics[idx + 1].title
      }” 🧀`;
    }
    if (idx >= 0 && idx === (wk.lesson_topics?.length ?? 0) - 1) {
      return `Check the Resources next to add an ingredient 🫑`;
    }

    if (activeSection === "resources") {
      return `Pass Week ${weekNum} quiz to add your ingredient 🥬`;
    }
    if (activeSection === "quiz") {
      const passed =
        (savedQuizResults[`week${weekNum}`]?.results?.percentage ?? 0) > 40;
      return passed
        ? `Nice! You added an ingredient. Continue to Week ${weekNum + 1} 🥪`
        : `Score above 40% to add this week’s ingredient 🥓`;
    }
    return null;
  };

  const isWeekUnlocked = (weekNumber: number) => {
    if (weekNumber === 1) return true;

    // Check if previous week's quiz is completed using saved results
    const prevWeekResult = savedQuizResults[`week${weekNumber - 1}`];
    return prevWeekResult && prevWeekResult.results?.percentage > 40; // Must score above 40% to unlock next week
  };

  const isWeekCompleted = (weekNumber: number) => {
    const weekLessons =
      courseData?.weeks?.[weekNumber - 1]?.lesson_topics || [];
    if (weekLessons.length === 0) return false;

    const weekLessonIds = weekLessons.map(
      (lesson: LessonTopic) => `week_${weekNumber}_${lesson.id}`
    );

    return weekLessonIds.every((id: string) => completedLessons.has(id));
  };

  const totalWeeks =
    courseData?.navigation?.total_weeks || courseData?.weeks?.length || 0;
  const progressPct = useMemo(() => {
    if (!courseData?.weeks?.length) return 0;

    // Count sections per week (overview + lessons + resources? + quiz)
    const countWeek = (wk: any) => {
      const lessons = wk.lesson_topics?.length ?? 0;
      const hasResources = !!wk.resources; // count only if exists
      // If every week always has a quiz, keep quiz=1; otherwise use !!wk.quiz ? 1 : 0
      const quiz = 1;

      const total = 1 /* overview */ + lessons + (hasResources ? 1 : 0) + quiz;

      // Completed:
      // - overview: count as done (baseline) since we always land here first
      let completed = 1;

      // - lessons: use your completedLessons set (week_<n>_<lesson.id>)
      if (lessons) {
        completed += (wk.lesson_topics || []).reduce((acc: number, ls: any) => {
          const id = `week_${wk.week_number}_${ls.id}`;
          return acc + (completedLessons.has(id) ? 1 : 0);
        }, 0);
      }

      // - resources: (optional) mark as done only if you want to track "visited"
      // For now we don't track visit, so keep 0. If you add tracking, toggle here.

      // - quiz: count when passed (> 40%)
      const quizPassed =
        (savedQuizResults[`week${wk.week_number}`]?.results?.percentage ?? 0) >
        40;
      if (quizPassed) completed += 1;

      return { total, completed };
    };

    const sum = courseData.weeks.reduce(
      (agg: { total: number; completed: number }, wk: any) => {
        const { total, completed } = countWeek(wk);
        return {
          total: agg.total + total,
          completed: agg.completed + completed,
        };
      },
      { total: 0, completed: 0 }
    );

    if (sum.total === 0) return 0;
    return Math.round((sum.completed / sum.total) * 100);
  }, [courseData?.weeks, completedLessons, savedQuizResults]);

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

  // helpers
  const getCurrentWeekData = () =>
    courseData?.weeks?.find((w: any) => w.week_number === weekNum);

  const gotoNext = () => {
    const wk = getCurrentWeekData();
    if (!wk) return;

    // overview → first lesson
    if (activeSection === "overview" && wk.lesson_topics?.[0]) {
      setActiveSection(wk.lesson_topics[0].id);
      return;
    }

    // lesson → next lesson | resources | quiz
    const idx =
      wk.lesson_topics?.findIndex((ls: any) => ls.id === activeSection) ?? -1;

    if (idx >= 0 && idx < wk.lesson_topics.length - 1) {
      setActiveSection(wk.lesson_topics[idx + 1].id);
      return;
    }

    if (activeSection !== "resources" && activeSection !== "quiz") {
      setActiveSection("resources");
      return;
    }

    if (activeSection === "resources") {
      setActiveSection("quiz");
      return;
    }
  };

  const gotoPrev = async () => {
    const wk = getCurrentWeekData();
    if (!wk) return;

    // quiz → resources
    if (activeSection === "quiz") {
      setActiveSection("resources");
      return;
    }

    // resources → last lesson | overview
    if (activeSection === "resources") {
      const lastLesson = wk.lesson_topics?.slice(-1)[0];
      if (lastLesson) setActiveSection(lastLesson.id);
      else setActiveSection("overview");
      return;
    }

    // lessons → previous lesson | overview
    const idx =
      wk.lesson_topics?.findIndex((ls: any) => ls.id === activeSection) ?? -1;

    if (idx > 0) {
      setActiveSection(wk.lesson_topics[idx - 1].id);
      return;
    }
    if (idx === 0) {
      setActiveSection("overview");
      return;
    }

    // overview at Week 1: nothing to do
    if (activeSection === "overview" && weekNum <= 1) return;

    // overview at Week N>1 → jump to previous week's quiz
    if (activeSection === "overview" && weekNum > 1) {
      await fetchWeek(weekNum - 1);
      setActiveSection("quiz");
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  return (
    <main className="relative max-w-7xl mx-auto lg:pl-80">
      <SideTaskbar
        courseData={courseData}
        weekNum={weekNum}
        totalWeeks={totalWeeks}
        progressPct={progressPct}
        savedQuizResults={savedQuizResults}
        completedLessons={completedLessons}
        activeSection={activeSection}
        onFetchWeek={(n) => fetchWeek(n)}
        onChangeActiveSection={setActiveSection}
      />

      <StudyTipsLoader
        open={tipsOpen}
        weekInfo={week ?? { week_number: weekNum }}
        courseContext={courseData}
        performance={{
          lastQuiz: savedQuizResults[`week${weekNum}`]?.results ?? null,
          overallProgress: Math.round(progressPct),
        }}
        iconSrc="/sandwich-ed.png"
      />

      {/* Main Content */}
      <section className="p-4 md:p-6 space-y-4">
        {/* Header bar */}
        <div className="rounded-2xl border p-3 sm:p-4">
          <div>
            <h1 className="text-2xl font-semibold">
              {week?.title || `Week ${weekNum}`}
            </h1>
            <p className="text-sm">Continue your personalized curriculum</p>
            {getNextIngredientPrompt() && (
              <div className="mt-2 inline-flex items-center rounded-lg border px-2.5 py-1 text-sm bg-yellow-50 border-yellow-200 text-yellow-800">
                {getNextIngredientPrompt()}
              </div>
            )}
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
                activeSection={activeSection}
                weekInfo={week}
                courseContext={courseData}
                onSectionChange={setActiveSection}
                onQuizComplete={(results: any, adaptationSummary?: any) => {
                  // Save quiz results to sessionStorage
                  const quizResults = {
                    weekNumber: weekNum,
                    results: results,
                    adaptationSummary: adaptationSummary,
                    completedAt: new Date().toISOString(),
                  };

                  // Save individual quiz result (session only)
                  sessionStorage.setItem(
                    `sessionQuizResult:week${weekNum}`,
                    JSON.stringify(quizResults)
                  );

                  // Update all quiz results (session only)
                  const allResults = JSON.parse(
                    sessionStorage.getItem("sessionQuizResults") || "{}"
                  );
                  allResults[`week${weekNum}`] = quizResults;
                  sessionStorage.setItem(
                    "sessionQuizResults",
                    JSON.stringify(allResults)
                  );
                  setSavedQuizResults(allResults);

                  // Mark quiz as completed and unlock next week if passed
                  if (results.percentage > 40) {
                    // Pass threshold - above 40%
                    const updatedWeeks = courseData.weeks.map((w: any) => {
                      if (w.week_number === weekNum) {
                        return { ...w, quiz_completed: true };
                      }
                      return w;
                    });
                    const updatedCourseData = {
                      ...courseData,
                      weeks: updatedWeeks,
                    };
                    setCourseData(updatedCourseData);
                    sessionStorage.setItem(
                      "courseData",
                      JSON.stringify(updatedCourseData)
                    );
                  }

                  // Force re-render by updating the week state
                  setWeek((prev) => (prev ? { ...prev } : null));
                }}
                onContinueToNextWeek={() => {
                  // Check if this was the last week and quiz was passed
                  if (weekNum >= totalWeeks) {
                    const lastQuizResult = savedQuizResults[`week${weekNum}`];
                    if (lastQuizResult?.results?.percentage > 40) {
                      // Course completed successfully - redirect to completion page
                      window.location.href = "/completion";
                      return;
                    }
                  }

                  if (weekNum < totalWeeks && isWeekUnlocked(weekNum + 1)) {
                    fetchWeek(weekNum + 1);
                    setActiveSection("overview"); // Go to overview of next week
                    // Expand the next week in sidebar
                    setExpandedWeeks((prev) => new Set([...prev, weekNum + 1]));
                  }
                }}
                onNavigateNext={() => {
                  const currentWeekData = courseData.weeks?.find(
                    (w: any) => w.week_number === weekNum
                  );
                  if (currentWeekData) {
                    // Navigate through sections: overview → lesson1 → lesson2 → ... → resources → quiz/assessment
                    if (
                      activeSection === "overview" &&
                      currentWeekData.lesson_topics?.[0]
                    ) {
                      // Go to first lesson
                      setActiveSection(currentWeekData.lesson_topics[0].id);
                    } else {
                      // Find current lesson and go to next lesson, or to resources if we're on the last lesson
                      const currentLessonIndex =
                        currentWeekData.lesson_topics?.findIndex(
                          (lesson: any) => lesson.id === activeSection
                        );

                      if (
                        currentLessonIndex >= 0 &&
                        currentLessonIndex <
                          currentWeekData.lesson_topics.length - 1
                      ) {
                        // Go to next lesson
                        setActiveSection(
                          currentWeekData.lesson_topics[currentLessonIndex + 1]
                            .id
                        );
                      } else if (
                        activeSection !== "resources" &&
                        activeSection !== "quiz"
                      ) {
                        // From last lesson, go to resources
                        setActiveSection("resources");
                      } else if (activeSection === "resources") {
                        setActiveSection("quiz");
                      }
                    }
                  }
                }}
                onLoadLesson={async (lessonInfo) => {
                  return await withTips(async () => {
                    const res = await fetch(
                      "http://localhost:8000/get_lesson_content",
                      {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                          lesson_info: lessonInfo,
                          course_context: courseData,
                        }),
                      }
                    );
                    const data = await res.json();
                    return data.lesson_content;
                  });
                }}
              />
            )}

            {/* Navigation buttons at bottom */}
            {!loading && (
              <div className="mt-6 pt-6 border-t">
                <div className="flex items-center justify-between">
                  {/* ← Previous (section-aware) */}
                  <Button
                    onClick={gotoPrev}
                    variant="outline"
                    className="bg-white text-blue-600 border-blue-600 hover:bg-blue-50"
                    // disable only when truly at the very start: Week 1 + overview
                    disabled={weekNum <= 1 && activeSection === "overview"}
                  >
                    ← Previous
                  </Button>

                  {/* Center status */}
                  <div className="flex items-center gap-4 text-sm text-white">
                    <span>
                      Week {weekNum} of {totalWeeks}
                    </span>
                    {savedQuizResults[`week${weekNum}`] && (
                      <span className="inline-flex items-center rounded-full border border-green-300 bg-green-50 px-2 py-0.5 text-xs text-green-600">
                        Quiz:{" "}
                        {savedQuizResults[`week${weekNum}`].results.percentage}%
                      </span>
                    )}
                  </div>

                  {/* → Next (keeps your quiz/continue logic) */}
                  {activeSection === "quiz" ? (
                    savedQuizResults[`week${weekNum}`]?.results?.percentage >=
                    60 ? (
                      <Button
                        onClick={() => {
                          if (weekNum >= totalWeeks) {
                            window.location.href = "/completion";
                          } else {
                            fetchWeek(weekNum + 1);
                            setActiveSection("overview");
                          }
                        }}
                        className="bg-green-600 hover:bg-green-700"
                      >
                        {weekNum >= totalWeeks
                          ? "Complete Course 🎉"
                          : `Continue to Week ${weekNum + 1} →`}
                      </Button>
                    ) : (
                      <Button
                        variant="outline"
                        className="bg-white text-blue-600 border-blue-600 hover:bg-blue-50"
                        disabled
                      >
                        Complete Quiz to Continue
                      </Button>
                    )
                  ) : (
                    <Button onClick={gotoNext}>Next →</Button>
                  )}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </section>
      <LessonChatbot courseContext={courseData} weekContext={week} />
    </main>
  );
}

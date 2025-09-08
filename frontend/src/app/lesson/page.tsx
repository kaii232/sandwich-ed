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

  const isWeekUnlocked = (weekNumber: number) => {
    if (weekNumber === 1) return true;

    // Check if previous week's quiz is completed using saved results
    const prevWeekResult = savedQuizResults[`week${weekNumber - 1}`];
    return prevWeekResult && prevWeekResult.results?.percentage >= 60;
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
    const completedWeeks = Array.from(
      { length: totalWeeks },
      (_, i) => i + 1
    ).filter((w) => isWeekCompleted(w)).length;
    return Math.min(100, Math.max(0, (completedWeeks / totalWeeks) * 100));
  }, [totalWeeks, completedLessons]);

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

      {/* <StudyTipsLoader
        open={tipsOpen}
        weekInfo={week ?? { week_number: weekNum }}
        courseContext={courseData}
        performance={{
          lastQuiz: savedQuizResults[`week${weekNum}`]?.results ?? null,
          overallProgress: Math.round(progressPct),
        }}
        iconSrc="/sandwich-ed.png"
      /> */}

      {/* Main Content */}
      <section className="p-4 md:p-6 space-y-4">
        {/* Header bar */}
        <div className="rounded-2xl border p-3 sm:p-4">
          <div>
            <h1 className="text-2xl font-semibold">
              {week?.title || `Week ${weekNum}`}
            </h1>
            <p className="text-sm">Continue your personalized curriculum</p>
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
                  if (results.percentage >= 60) {
                    // Pass threshold
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
                    if (lastQuizResult?.results?.percentage >= 60) {
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
                  <Button
                    onClick={() => {
                      if (weekNum > 1) fetchWeek(weekNum - 1);
                    }}
                    variant="outline"
                    className="bg-white text-blue-600 border-blue-600 hover:bg-blue-50"
                    disabled={weekNum <= 1}
                  >
                    ← Previous Week
                  </Button>

                  {/* Center content showing current status */}
                  <div className="flex items-center gap-4 text-sm text-neutral-600">
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

                  {/* Smart Next Button */}
                  {activeSection === "quiz" ? (
                    // On quiz page - show different states
                    savedQuizResults[`week${weekNum}`]?.results?.percentage >=
                    60 ? (
                      // Quiz passed - show continue to next week or completion
                      <Button
                        onClick={() => {
                          if (weekNum >= totalWeeks) {
                            // Course completed - go to completion page
                            window.location.href = "/completion";
                          } else if (weekNum < totalWeeks) {
                            fetchWeek(weekNum + 1);
                            setActiveSection("overview");
                            setExpandedWeeks(
                              (prev) => new Set([...prev, weekNum + 1])
                            );
                          }
                        }}
                        className="bg-green-600 hover:bg-green-700"
                      >
                        {weekNum >= totalWeeks
                          ? "Complete Course 🎉"
                          : "Continue to Week " + (weekNum + 1) + " →"}
                      </Button>
                    ) : (
                      // Quiz not completed yet - show encouragement to complete
                      <Button disabled variant="outline">
                        Complete Quiz to Continue
                      </Button>
                    )
                  ) : (
                    // On other content pages - show regular next navigation
                    <Button
                      onClick={() => {
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
                            setActiveSection(
                              currentWeekData.lesson_topics[0].id
                            );
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
                                currentWeekData.lesson_topics[
                                  currentLessonIndex + 1
                                ].id
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
                      disabled={activeSection === "quiz"}
                    >
                      Next →
                    </Button>
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

"use client";
import { useEffect, useMemo, useState } from "react";
import { getWeekContent } from "@/lib/api";
import WeekViewer from "@/components/WeekViewer";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { ChevronDown, ChevronRight, Lock, CheckCircle, PlayCircle, BookOpen, Target } from "lucide-react";

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
  const [expandedLessons, setExpandedLessons] = useState<Set<string>>(new Set());
  const [completedLessons, setCompletedLessons] = useState<Set<string>>(new Set());
  const [activeSection, setActiveSection] = useState<string>("overview");
  const [savedQuizResults, setSavedQuizResults] = useState<Record<string, any>>({});

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
    const existingResults = sessionStorage.getItem('sessionQuizResults');
    if (!existingResults) {
      // Fresh session - ensure everything is clear
      sessionStorage.removeItem('sessionQuizResults');
      sessionStorage.removeItem('allQuizResults'); // Also clear old key
      setSavedQuizResults({});
    } else {
      // Load existing session results
      const allResults = JSON.parse(existingResults || '{}');
      setSavedQuizResults(allResults);
    }
    
    // Mark session as active
    sessionStorage.setItem('currentSessionActive', 'true');

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
      
      // Expand current week in sidebar
      setExpandedWeeks(prev => new Set([...prev, targetWeek]));
    } catch (e: any) {
      setError(e?.message || "Failed to load week content.");
    } finally {
      setLoading(false);
    }
  }

  const toggleWeekExpansion = (weekNumber: number) => {
    setExpandedWeeks(prev => {
      const newSet = new Set(prev);
      if (newSet.has(weekNumber)) {
        newSet.delete(weekNumber);
      } else {
        newSet.add(weekNumber);
      }
      return newSet;
    });
  };

  const toggleLessonExpansion = (lessonId: string) => {
    setExpandedLessons(prev => {
      const newSet = new Set(prev);
      if (newSet.has(lessonId)) {
        newSet.delete(lessonId);
      } else {
        newSet.add(lessonId);
      }
      return newSet;
    });
  };

  const markLessonComplete = (lessonId: string) => {
    setCompletedLessons(prev => {
      const newSet = new Set([...prev, lessonId]);
      sessionStorage.setItem("completedLessons", JSON.stringify([...newSet]));
      return newSet;
    });
  };

  const isWeekUnlocked = (weekNumber: number) => {
    if (weekNumber === 1) return true;
    
    // Check if previous week's quiz is completed using saved results
    const prevWeekResult = savedQuizResults[`week${weekNumber - 1}`];
    return prevWeekResult && prevWeekResult.results?.percentage >= 60;
  };

  const isWeekCompleted = (weekNumber: number) => {
    const weekLessons = courseData?.weeks?.[weekNumber - 1]?.lesson_topics || [];
    if (weekLessons.length === 0) return false;
    
    const weekLessonIds = weekLessons.map((lesson: LessonTopic) => 
      `week_${weekNumber}_${lesson.id}`
    );
    
    return weekLessonIds.every((id: string) => completedLessons.has(id));
  };

  const totalWeeks = courseData?.navigation?.total_weeks || courseData?.weeks?.length || 0;
  const progressPct = useMemo(() => {
    const completedWeeks = Array.from({ length: totalWeeks }, (_, i) => i + 1)
      .filter(w => isWeekCompleted(w)).length;
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
    <main className="max-w-7xl mx-auto p-4 md:p-6 grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-4">
      {/* Enhanced Coursera-style Sidebar */}
      <aside className="lg:sticky lg:top-6 h-fit max-h-[calc(100vh-3rem)] overflow-y-auto">
        <Card className="rounded-2xl">
          <CardHeader>
            <div className="flex items-start justify-between gap-2">
              <div>
                <CardTitle className="text-lg">
                  {courseData.summary?.course_title || "Your Course"}
                </CardTitle>
                <p className="text-xs text-neutral-600 mt-1">
                  {courseData.summary?.difficulty || "Beginner"} • {totalWeeks} weeks
                </p>
              </div>
              <Badge>Week {weekNum}</Badge>
            </div>
          </CardHeader>
          
          <CardContent className="space-y-4">
            {/* Progress */}
            <div>
              <div className="flex items-center justify-between text-sm mb-2">
                <span>Overall Progress</span>
                <span className="text-neutral-600">{Math.round(progressPct)}%</span>
              </div>
              <Progress value={progressPct} />
            </div>

            {/* Quiz History Summary - Session Only */}
            {Object.keys(savedQuizResults).length > 0 && (
              <div className="border-t pt-4">
                <div className="text-xs uppercase tracking-wide text-neutral-500 mb-2">
                  Current Session Results
                </div>
                <div className="space-y-1">
                  {Object.entries(savedQuizResults).map(([weekKey, result]: [string, any]) => (
                    <div key={weekKey} className="flex items-center justify-between text-sm">
                      <span className="text-neutral-700">
                        {weekKey.replace('week', 'Week ')}
                      </span>
                      <span className={`font-medium ${
                        result.results.percentage >= 90 ? 'text-green-600' :
                        result.results.percentage >= 70 ? 'text-blue-600' :
                        result.results.percentage >= 60 ? 'text-yellow-600' : 'text-red-600'
                      }`}>
                        {result.results.percentage}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Week List with Lessons */}
            <div className="border-t pt-4 space-y-1">
              <div className="text-xs uppercase tracking-wide text-neutral-500 mb-3">
                Course Content
              </div>
              
              {courseData.weeks?.map((weekData: any, index: number) => {
                const weekNumber = weekData.week_number || index + 1;
                const isUnlocked = isWeekUnlocked(weekNumber);
                const isCompleted = isWeekCompleted(weekNumber);
                const isExpanded = expandedWeeks.has(weekNumber);
                const isCurrent = weekNumber === weekNum;
                
                return (
                  <div key={weekNumber} className="space-y-1">
                    {/* Week Header */}
                    <button
                      onClick={() => {
                        if (isUnlocked) {
                          toggleWeekExpansion(weekNumber);
                          if (!isExpanded) {
                            fetchWeek(weekNumber);
                          }
                        }
                      }}
                      disabled={!isUnlocked}
                      className={`w-full flex items-center gap-2 p-3 rounded-lg text-left transition-all ${
                        isCurrent
                          ? "bg-blue-50 border border-blue-200"
                          : isUnlocked
                          ? "hover:bg-neutral-50 border border-transparent"
                          : "bg-neutral-50 border border-transparent cursor-not-allowed"
                      }`}
                    >
                      <div className="flex-shrink-0">
                        {!isUnlocked ? (
                          <Lock className="w-4 h-4 text-neutral-400" />
                        ) : isCompleted ? (
                          <CheckCircle className="w-4 h-4 text-green-500" />
                        ) : isExpanded ? (
                          <ChevronDown className="w-4 h-4 text-neutral-600" />
                        ) : (
                          <ChevronRight className="w-4 h-4 text-neutral-600" />
                        )}
                      </div>
                      
                      <div className="flex-1 min-w-0">
                        <div className={`text-sm font-medium ${!isUnlocked ? 'text-neutral-400' : 'text-neutral-900'}`}>
                          Week {weekNumber}
                        </div>
                        <div className={`text-xs truncate ${!isUnlocked ? 'text-neutral-400' : 'text-neutral-600'}`}>
                          {weekData.title?.replace(`Week ${weekNumber}: `, '') || 'Loading...'}
                        </div>
                      </div>
                    </button>

                    {/* Week Content - Only show if expanded and unlocked */}
                    {isExpanded && isUnlocked && (
                      <div className="ml-6 space-y-1 pb-2">
                        {/* Week Overview */}
                        <button
                          onClick={() => {
                            fetchWeek(weekNumber);
                            setActiveSection("overview");
                          }}
                          className={`w-full flex items-center gap-2 p-2 rounded text-left text-sm transition ${
                            isCurrent && activeSection === "overview"
                              ? "bg-blue-100 text-blue-700"
                              : "hover:bg-neutral-50 text-neutral-700"
                          }`}
                        >
                          <Target className="w-3.5 h-3.5" />
                          <span>Week Overview & Objectives</span>
                        </button>

                        {/* Lesson Topics */}
                        {weekData.lesson_topics?.map((lesson: LessonTopic, lessonIndex: number) => {
                          const lessonId = `week_${weekNumber}_${lesson.id}`;
                          const isLessonCompleted = completedLessons.has(lessonId);
                          
                          return (
                            <div key={lesson.id}>
                              <button
                                onClick={() => {
                                  fetchWeek(weekNumber);
                                  setActiveSection(lesson.id);
                                  toggleLessonExpansion(lesson.id);
                                }}
                                className={`w-full flex items-center gap-2 p-2 rounded text-left text-sm transition ${
                                  isCurrent && activeSection === lesson.id
                                    ? "bg-blue-100 text-blue-700"
                                    : "hover:bg-neutral-50 text-neutral-700"
                                }`}
                              >
                                <div className="flex-shrink-0">
                                  {isLessonCompleted ? (
                                    <CheckCircle className="w-3.5 h-3.5 text-green-500" />
                                  ) : (
                                    <PlayCircle className="w-3.5 h-3.5 text-neutral-500" />
                                  )}
                                </div>
                                <span className="truncate">{lesson.title}</span>
                              </button>
                            </div>
                          );
                        })}

                        {/* Additional Resources */}
                        <button
                          onClick={() => {
                            fetchWeek(weekNumber);
                            setActiveSection("resources");
                          }}
                          className={`w-full flex items-center gap-2 p-2 rounded text-left text-sm transition ${
                            isCurrent && activeSection === "resources"
                              ? "bg-blue-100 text-blue-700"
                              : "hover:bg-neutral-50 text-neutral-700"
                          }`}
                        >
                          <BookOpen className="w-3.5 h-3.5" />
                          <span>Additional Resources</span>
                        </button>

                        {/* Quiz or Assessment Guide */}
                        <button
                          onClick={() => {
                            fetchWeek(weekNumber);
                            setActiveSection("quiz");
                          }}
                          className={`w-full flex items-center gap-2 p-2 rounded text-left text-sm transition ${
                            isCurrent && activeSection === "quiz"
                              ? "bg-blue-100 text-blue-700"
                              : "hover:bg-neutral-50 text-neutral-700"
                          }`}
                        >
                          <div className="flex-shrink-0">
                            {savedQuizResults[`week${weekNumber}`]?.results?.percentage >= 60 ? (
                              <CheckCircle className="w-3.5 h-3.5 text-green-500" />
                            ) : (
                              <Target className="w-3.5 h-3.5 text-neutral-500" />
                            )}
                          </div>
                          <span>
                            {weekNumber >= totalWeeks ? "Assessment Guide" : "Quiz"}
                          </span>
                          {savedQuizResults[`week${weekNumber}`] && (
                            <span className="ml-auto text-xs text-green-600 font-medium">
                              {savedQuizResults[`week${weekNumber}`].results.percentage}%
                            </span>
                          )}
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      </aside>

      {/* Main Content */}
      <section className="space-y-4">
        {/* Header bar */}
        <div className="rounded-2xl border bg-white p-3 sm:p-4">
          <div>
            <h1 className="text-2xl font-semibold">
              {week?.title || `Week ${weekNum}`}
            </h1>
            <p className="text-sm text-neutral-600">
              Continue your personalized curriculum
            </p>
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
                    completedAt: new Date().toISOString()
                  };
                  
                  // Save individual quiz result (session only)
                  sessionStorage.setItem(`sessionQuizResult:week${weekNum}`, JSON.stringify(quizResults));
                  
                  // Update all quiz results (session only)
                  const allResults = JSON.parse(sessionStorage.getItem('sessionQuizResults') || '{}');
                  allResults[`week${weekNum}`] = quizResults;
                  sessionStorage.setItem('sessionQuizResults', JSON.stringify(allResults));
                  setSavedQuizResults(allResults);
                  
                  // Mark quiz as completed and unlock next week if passed
                  if (results.percentage >= 60) { // Pass threshold
                    const updatedWeeks = courseData.weeks.map((w: any) => {
                      if (w.week_number === weekNum) {
                        return { ...w, quiz_completed: true };
                      }
                      return w;
                    });
                    const updatedCourseData = { ...courseData, weeks: updatedWeeks };
                    setCourseData(updatedCourseData);
                    sessionStorage.setItem("courseData", JSON.stringify(updatedCourseData));
                  }
                  
                  // Force re-render by updating the week state
                  setWeek(prev => prev ? {...prev} : null);
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
                    setExpandedWeeks(prev => new Set([...prev, weekNum + 1]));
                  }
                }}
                onNavigateNext={() => {
                  const currentWeekData = courseData.weeks?.find((w: any) => w.week_number === weekNum);
                  if (currentWeekData) {
                    // Navigate through sections: overview → lesson1 → lesson2 → ... → resources → quiz/assessment
                    if (activeSection === "overview" && currentWeekData.lesson_topics?.[0]) {
                      // Go to first lesson
                      setActiveSection(currentWeekData.lesson_topics[0].id);
                    } else {
                      // Find current lesson and go to next lesson, or to resources if we're on the last lesson
                      const currentLessonIndex = currentWeekData.lesson_topics?.findIndex((lesson: any) => lesson.id === activeSection);
                      
                      if (currentLessonIndex >= 0 && currentLessonIndex < currentWeekData.lesson_topics.length - 1) {
                        // Go to next lesson
                        setActiveSection(currentWeekData.lesson_topics[currentLessonIndex + 1].id);
                      } else if (activeSection !== "resources" && activeSection !== "quiz") {
                        // From last lesson, go to resources
                        setActiveSection("resources");
                      } else if (activeSection === "resources") {
                        setActiveSection("quiz");
                      }
                    }
                  }
                }}
                onLoadLesson={async (lessonInfo) => {
                  try {
                    const res = await fetch("http://localhost:8000/get_lesson_content", {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({
                        lesson_info: lessonInfo,
                        course_context: courseData,
                      }),
                    });
                    const data = await res.json();
                    return data.lesson_content;
                  } catch (e) {
                    console.error(e);
                    return null;
                  }
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
                    disabled={weekNum <= 1}
                    variant="outline"
                  >
                    ← Previous Week
                  </Button>
                  
                  {/* Center content showing current status */}
                  <div className="flex items-center gap-4 text-sm text-neutral-600">
                    <span>Week {weekNum} of {totalWeeks}</span>
                    {savedQuizResults[`week${weekNum}`] && (
                      <span className="inline-flex items-center rounded-full border border-green-300 bg-green-50 px-2 py-0.5 text-xs text-green-600">
                        Quiz: {savedQuizResults[`week${weekNum}`].results.percentage}%
                      </span>
                    )}
                  </div>
                  
                  {/* Smart Next Button */}
                  {activeSection === "quiz" ? (
                    // On quiz page - show different states
                    savedQuizResults[`week${weekNum}`]?.results?.percentage >= 60 ? (
                      // Quiz passed - show continue to next week or completion
                      <Button 
                        onClick={() => {
                          if (weekNum >= totalWeeks) {
                            // Course completed - go to completion page
                            window.location.href = "/completion";
                          } else if (weekNum < totalWeeks) {
                            fetchWeek(weekNum + 1);
                            setActiveSection("overview");
                            setExpandedWeeks(prev => new Set([...prev, weekNum + 1]));
                          }
                        }} 
                        className="bg-green-600 hover:bg-green-700"
                      >
                        {weekNum >= totalWeeks ? "Complete Course 🎉" : "Continue to Week " + (weekNum + 1) + " →"}
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
                        const currentWeekData = courseData.weeks?.find((w: any) => w.week_number === weekNum);
                        if (currentWeekData) {
                          // Navigate through sections: overview → lesson1 → lesson2 → ... → resources → quiz/assessment
                          if (activeSection === "overview" && currentWeekData.lesson_topics?.[0]) {
                            // Go to first lesson
                            setActiveSection(currentWeekData.lesson_topics[0].id);
                          } else {
                            // Find current lesson and go to next lesson, or to resources if we're on the last lesson
                            const currentLessonIndex = currentWeekData.lesson_topics?.findIndex((lesson: any) => lesson.id === activeSection);
                            
                            if (currentLessonIndex >= 0 && currentLessonIndex < currentWeekData.lesson_topics.length - 1) {
                              // Go to next lesson
                              setActiveSection(currentWeekData.lesson_topics[currentLessonIndex + 1].id);
                            } else if (activeSection !== "resources" && activeSection !== "quiz") {
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
    </main>
  );
}
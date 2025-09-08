"use client";

import { useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import Sandwich from "@/components/Sandwich";

import {
  BookOpen,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Lock,
  Menu,
  Target,
  X,
  PlayCircle,
} from "lucide-react";

type LessonTopic = {
  id: string;
  title: string;
};

type WeekItem = {
  week_number: number;
  title?: string;
  lesson_topics?: LessonTopic[];
  quiz_completed?: boolean;
};

interface SideTaskbarProps {
  /** Full course data from session (contains weeks, summary, etc.) */
  courseData: {
    summary?: { course_title?: string; difficulty?: string };
    weeks?: WeekItem[];
  } | null;

  /** Current week number (1-based) */
  weekNum: number;

  /** Total number of weeks */
  totalWeeks: number;

  /** Overall completion percentage (0..100) */
  progressPct: number;

  /** Session-only quiz results map: { week1: {...}, week2: {...}, ... } */
  savedQuizResults: Record<string, any>;

  /** Set of completed lesson ids: e.g., Set(["week_1_xyz", ...]) */
  completedLessons: Set<string>;

  /** Which section is currently opened in the main content (overview | lessonId | resources | quiz) */
  activeSection: string;

  /** Load a target week’s content; used for navigation */
  onFetchWeek: (weekNumber: number) => void | Promise<void>;

  /** Switch the active section in main content */
  onChangeActiveSection: (sectionId: string) => void;
}

export default function SideTaskbar({
  courseData,
  weekNum,
  totalWeeks,
  progressPct,
  savedQuizResults,
  completedLessons,
  activeSection,
  onFetchWeek,
  onChangeActiveSection,
}: SideTaskbarProps) {
  // Drawer open state: open on desktop by default, closed on mobile
  const [isOpen, setIsOpen] = useState(false);

  // Expand current week by default
  const [expandedWeeks, setExpandedWeeks] = useState<Set<number>>(
    new Set([weekNum || 1])
  );

  // Open/close defaults by viewport
  useEffect(() => {
    const sync = () => setIsOpen(window.innerWidth >= 1024); // lg breakpoint
    sync();
    window.addEventListener("resize", sync);
    return () => window.removeEventListener("resize", sync);
  }, []);

  // When week changes, ensure it’s expanded
  useEffect(() => {
    setExpandedWeeks((prev) => new Set([...prev, weekNum]));
  }, [weekNum]);

  // Derived helpers (kept local so parent stays lean)

  const isWeekUnlocked = (n: number) => {
    if (n === 1) return true;
    const prev = savedQuizResults[`week${n - 1}`];
    return !!(prev && prev.results?.percentage > 40); // Must score above 40% to unlock next week
  };

  const isWeekCompleted = (n: number) => {
    const wk = courseData?.weeks?.[n - 1];
    const lessons = wk?.lesson_topics ?? [];
    if (!lessons.length) return false;
    return lessons
      .map((ls) => `week_${n}_${ls.id}`)
      .every((id) => completedLessons.has(id));
  };

  const courseTitle = courseData?.summary?.course_title || "Your Course";
  const difficulty = courseData?.summary?.difficulty || "Beginner";

  // UI handlers

  const toggleWeekExpansion = (n: number) => {
    setExpandedWeeks((prev) => {
      const next = new Set(prev);
      if (next.has(n)) next.delete(n);
      else next.add(n);
      return next;
    });
  };

  const goWeekSection = (n: number, sectionId: string) => {
    // Ensure week data is fetched and switch section
    onFetchWeek(n);
    onChangeActiveSection(sectionId);
    // Close drawer on mobile
    if (window.innerWidth < 1024) setIsOpen(false);
  };

  // --- Render ---

  return (
    <>
      {/* Floating mobile toggle button (hidden on desktop) */}
      <button
        aria-label="Open sidebar"
        onClick={() => setIsOpen(true)}
        className="lg:hidden fixed left-3 top-3 z-[60] inline-flex items-center gap-2 rounded-lg border bg-white text-black px-3 py-2 text-sm shadow-sm"
      >
        <Menu className="h-4 w-4" />
        Course
      </button>

      {/* Overlay for mobile */}
      <div
        className={`fixed inset-0 z-40 bg-black/30 backdrop-blur-sm transition-opacity lg:hidden ${
          isOpen
            ? "opacity-100 pointer-events-auto"
            : "opacity-0 pointer-events-none"
        }`}
        onClick={() => setIsOpen(false)}
      />

      {/* Sidebar drawer (mobile) + dock (desktop) */}
      <aside
        className={`fixed left-0 top-0 z-50 h-dvh w-80 bg-white text-black border-r shadow-sm
        transition-transform duration-300 ease-out
        ${isOpen ? "translate-x-0" : "-translate-x-full"}
        lg:translate-x-0`}
        aria-label="Course sidebar"
      >
        {/* Mobile header w/ close */}
        <div className="lg:hidden flex items-center justify-between px-3 py-3 border-b">
          <div className="text-sm font-medium">{courseTitle}</div>
          <button
            aria-label="Close sidebar"
            onClick={() => setIsOpen(false)}
            className="inline-flex items-center rounded-lg border px-2.5 py-1.5 text-sm hover:bg-neutral-50"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Scrollable content */}
        <div className="h-[calc(100dvh-0px)] lg:h-dvh overflow-y-auto px-3 pb-6">
          {/* Header card */}
          <div className="rounded-2xl border overflow-hidden mt-3">
            <div className="p-4 border-b">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="text-lg font-semibold">{courseTitle}</div>
                  <p className="text-xs text-neutral-600 mt-1">
                    {difficulty} • {totalWeeks} weeks
                  </p>
                </div>
                <Badge>Week {weekNum}</Badge>
              </div>
            </div>

            <div className="p-4 space-y-4">
              <div className="flex justify-center my-4">
                <Sandwich
                  totalWeeks={totalWeeks}
                  /* mark unlocked weeks from your savedQuizResults */
                  progress={Array.from({ length: totalWeeks }, (_, i) => ({
                    week: i + 1,
                    unlocked:
                      (savedQuizResults[`week${i + 1}`]?.results?.percentage ??
                        0) > 40,
                  }))}
                  themeOffset={0} // try 0..4 to vary first filling
                  width={320}
                  overlap={20}
                  showLockedDimmed // show every week; locked ones are dimmed
                  altPrefix="Learning geometry"
                />
              </div>

              {/* Progress */}
              <div>
                <div className="flex items-center justify-between text-sm mb-2">
                  <span>Overall Progress</span>
                  <span className="text-neutral-600">
                    {Math.round(progressPct)}%
                  </span>
                </div>
                <Progress value={progressPct} />
              </div>

              {/* Session results */}
              {Object.keys(savedQuizResults).length > 0 && (
                <div className="border-t pt-4">
                  <div className="text-xs uppercase tracking-wide text-neutral-500 mb-2">
                    Current Session Results
                  </div>
                  <div className="space-y-1">
                    {Object.entries(savedQuizResults).map(
                      ([weekKey, result]: [string, any]) => (
                        <div
                          key={weekKey}
                          className="flex items-center justify-between text-sm"
                        >
                          <span className="text-neutral-700">
                            {weekKey.replace("week", "Week ")}
                          </span>
                          <span
                            className={`font-medium ${
                              result.results.percentage >= 90
                                ? "text-green-600"
                                : result.results.percentage >= 80
                                ? "text-blue-600"
                                : result.results.percentage >= 60
                                ? "text-yellow-600"
                                : result.results.percentage > 40
                                ? "text-orange-600"
                                : "text-red-600"
                            }`}
                          >
                            {result.results.percentage}%
                          </span>
                        </div>
                      )
                    )}
                  </div>
                </div>
              )}

              {/* Week list */}
              <div className="border-t pt-4 space-y-1">
                <div className="text-xs uppercase tracking-wide text-neutral-500 mb-3">
                  Course Content
                </div>

                {(courseData?.weeks ?? []).map((weekData, idx) => {
                  const n = weekData.week_number || idx + 1;
                  const unlocked = isWeekUnlocked(n);
                  const completed = isWeekCompleted(n);
                  const expanded = expandedWeeks.has(n);
                  const current = n === weekNum;

                  return (
                    <div key={n} className="space-y-1">
                      {/* Week header */}
                      <button
                        onClick={() => {
                          if (unlocked) {
                            // expand/collapse and fetch on first open
                            const willOpen = !expanded;
                            toggleWeekExpansion(n);
                            if (willOpen) onFetchWeek(n);
                          }
                        }}
                        disabled={!unlocked}
                        className={`w-full flex items-center gap-2 p-3 rounded-lg text-left transition-all ${
                          current
                            ? "bg-blue-50 border border-blue-200"
                            : unlocked
                            ? "hover:bg-neutral-50 border border-transparent"
                            : "bg-neutral-50 border border-transparent cursor-not-allowed"
                        }`}
                      >
                        <div className="flex-shrink-0">
                          {!unlocked ? (
                            <Lock className="w-4 h-4 text-neutral-400" />
                          ) : completed ? (
                            <CheckCircle className="w-4 h-4 text-green-500" />
                          ) : expanded ? (
                            <ChevronDown className="w-4 h-4 text-neutral-600" />
                          ) : (
                            <ChevronRight className="w-4 h-4 text-neutral-600" />
                          )}
                        </div>

                        <div className="flex-1 min-w-0">
                          <div
                            className={`text-sm font-medium ${
                              !unlocked
                                ? "text-neutral-400"
                                : "text-neutral-900"
                            }`}
                          >
                            Week {n}
                          </div>
                          <div
                            className={`text-xs truncate ${
                              !unlocked
                                ? "text-neutral-400"
                                : "text-neutral-600"
                            }`}
                          >
                            {weekData.title?.replace(`Week ${n}: `, "") ||
                              "Loading..."}
                          </div>
                        </div>
                      </button>

                      {/* Week content */}
                      {expanded && unlocked && (
                        <div className="ml-6 space-y-1 pb-2">
                          {/* Overview */}
                          <button
                            onClick={() => goWeekSection(n, "overview")}
                            className={`w-full flex items-center gap-2 p-2 rounded text-left text-sm transition ${
                              current && activeSection === "overview"
                                ? "bg-blue-100 text-blue-700"
                                : "hover:bg-neutral-50 text-neutral-700"
                            }`}
                          >
                            <Target className="w-3.5 h-3.5" />
                            <span>Week Overview & Objectives</span>
                          </button>

                          {/* Lessons */}
                          {(weekData.lesson_topics ?? []).map((lesson) => {
                            const lessonId = `week_${n}_${lesson.id}`;
                            const done = completedLessons.has(lessonId);
                            const isActive =
                              current && activeSection === lesson.id;

                            return (
                              <div key={lesson.id}>
                                <button
                                  onClick={() => goWeekSection(n, lesson.id)}
                                  className={`w-full flex items-center gap-2 p-2 rounded text-left text-sm transition ${
                                    isActive
                                      ? "bg-blue-100 text-blue-700"
                                      : "hover:bg-neutral-50 text-neutral-700"
                                  }`}
                                >
                                  <div className="flex-shrink-0">
                                    {done ? (
                                      <CheckCircle className="w-3.5 h-3.5 text-green-500" />
                                    ) : (
                                      <PlayCircle className="w-3.5 h-3.5 text-neutral-500" />
                                    )}
                                  </div>
                                  <span className="truncate">
                                    {lesson.title}
                                  </span>
                                </button>
                              </div>
                            );
                          })}

                          {/* Resources */}
                          <button
                            onClick={() => goWeekSection(n, "resources")}
                            className={`w-full flex items-center gap-2 p-2 rounded text-left text-sm transition ${
                              current && activeSection === "resources"
                                ? "bg-blue-100 text-blue-700"
                                : "hover:bg-neutral-50 text-neutral-700"
                            }`}
                          >
                            <BookOpen className="w-3.5 h-3.5" />
                            <span>Additional Resources</span>
                          </button>

                          {/* Quiz */}
                          <button
                            onClick={() => goWeekSection(n, "quiz")}
                            className={`w-full flex items-center gap-2 p-2 rounded text-left text-sm transition ${
                              current && activeSection === "quiz"
                                ? "bg-blue-100 text-blue-700"
                                : "hover:bg-neutral-50 text-neutral-700"
                            }`}
                          >
                            <div className="flex-shrink-0">
                              {savedQuizResults[`week${n}`]?.results
                                ?.percentage > 40 ? (
                                <CheckCircle className="w-3.5 h-3.5 text-green-500" />
                              ) : (
                                <Target className="w-3.5 h-3.5 text-neutral-500" />
                              )}
                            </div>
                            <span>
                              {n >= totalWeeks ? "Assessment Guide" : "Quiz"}
                            </span>
                            {savedQuizResults[`week${n}`] && (
                              <span className="ml-auto text-xs text-green-600 font-medium">
                                {
                                  savedQuizResults[`week${n}`].results
                                    .percentage
                                }
                                %
                              </span>
                            )}
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* Desktop spacer so content doesn't sit under the docked sidebar */}
      <div className="hidden lg:block w-80 shrink-0" aria-hidden />
    </>
  );
}

"use client";
import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import Sandwich from "@/components/Sandwich";
import { Badge } from "@/components/ui/badge";
import {
  CheckCircle,
  Trophy,
  Star,
  BookOpen,
  Target,
  Download,
  Home,
} from "lucide-react";
import { useRouter } from "next/navigation";

export default function CompletionPage() {
  const [courseData, setCourseData] = useState<any>(null);
  const [quizResults, setQuizResults] = useState<Record<string, any>>({});
  const [overallStats, setOverallStats] = useState<any>(null);
  const router = useRouter();

  const totalWeeks =
    courseData?.weeks?.length ??
    courseData?.navigation?.total_weeks ??
    Object.keys(quizResults).length ??
    0;

  useEffect(() => {
    // Load course data
    const cd = sessionStorage.getItem("courseData");
    if (cd) {
      setCourseData(JSON.parse(cd));
    }

    // Load quiz results
    const results = sessionStorage.getItem("sessionQuizResults");
    if (results) {
      const allResults = JSON.parse(results);
      setQuizResults(allResults);

      // Calculate overall statistics
      const weeks = Object.values(allResults) as any[];
      const totalQuizzes = weeks.length;
      const averageScore =
        weeks.reduce(
          (acc: number, week: any) => acc + week.results.percentage,
          0
        ) / totalQuizzes;
      const highestScore = Math.max(
        ...weeks.map((week: any) => week.results.percentage)
      );
      const passedQuizzes = weeks.filter(
        (week: any) => week.results.percentage > 40
      ).length;

      setOverallStats({
        totalQuizzes,
        averageScore: Math.round(averageScore * 10) / 10,
        highestScore,
        passedQuizzes,
        coursePassRate: Math.round((passedQuizzes / totalQuizzes) * 100),
      });
    }
  }, []);

  const handleStartNewCourse = () => {
    // Clear all session data
    sessionStorage.removeItem("courseData");
    sessionStorage.removeItem("sessionQuizResults");
    sessionStorage.removeItem("currentWeek");
    sessionStorage.removeItem("completedLessons");
    sessionStorage.removeItem("currentSessionActive");

    // Clear week content cache
    Object.keys(sessionStorage).forEach((key) => {
      if (key.startsWith("weekContent:")) {
        sessionStorage.removeItem(key);
      }
    });

    // Navigate to home
    router.push("/");
  };

  const handleDownloadCertificate = () => {
    // In a real implementation, this would generate and download a certificate
    alert("Certificate download feature will be implemented soon!");
  };

  if (!courseData || !overallStats) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-green-50 to-blue-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600 mx-auto mb-4"></div>
          <p className="text-neutral-600">Loading completion summary...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen  from-green-50 to-blue-50 py-8">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="text-center mb-8">
          {/* Full sandwich reward */}
          <div className="mt-6 mb-8 flex flex-col items-center gap-3">
            <div className="inline-flex items-center rounded-full border px-3 py-1 text-sm bg-emerald-50 border-emerald-200 text-emerald-800">
              You have your sandwich ready! 🥪
            </div>

            <div className="flex justify-center">
              <Sandwich
                totalWeeks={totalWeeks}
                // fully unlocked so it renders a complete stack
                progress={Array.from({ length: totalWeeks }, (_, i) => ({
                  week: i + 1,
                  unlocked: true,
                }))}
                width={220}
                overlap={16}
                showLockedDimmed
                altPrefix={courseData.summary?.course_title || "Course"}
              />
            </div>
          </div>

          <div className="inline-flex items-center justify-center w-20 h-20 bg-green-100 rounded-full mb-4">
            <Trophy className="w-10 h-10 text-green-600" />
          </div>
          <h1 className="text-4xl font-bold  mb-2">🎉 Congratulations!</h1>
          <p className="text-xl text-gray-300 mb-4">
            You've successfully completed the course
          </p>
          <h2 className="text-2xl font-semibold text-green-700">
            {courseData.summary?.course_title || "Your Course"}
          </h2>
          <div className="inline-flex items-center rounded-full border px-2 py-0.5 text-xs mt-2 bg-green-100 text-green-800 border-green-300">
            {courseData.summary?.difficulty || "Beginner"} Level
          </div>
        </div>

        <div className="grid gap-6 md:grid-cols-2">
          {/* Course Overview */}
          <Card className="md:col-span-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BookOpen className="w-5 h-5" />
                Course Summary
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-blue-50 p-4 rounded-lg text-center">
                  <div className="text-2xl font-bold text-blue-600">
                    {overallStats.totalQuizzes}
                  </div>
                  <div className="text-sm text-blue-800">Quizzes Completed</div>
                </div>
                <div className="bg-green-50 p-4 rounded-lg text-center">
                  <div className="text-2xl font-bold text-green-600">
                    {overallStats.averageScore}%
                  </div>
                  <div className="text-sm text-green-800">Average Score</div>
                </div>
                <div className="bg-purple-50 p-4 rounded-lg text-center">
                  <div className="text-2xl font-bold text-purple-600">
                    {overallStats.highestScore}%
                  </div>
                  <div className="text-sm text-purple-800">Highest Score</div>
                </div>
                <div className="bg-yellow-50 p-4 rounded-lg text-center">
                  <div className="text-2xl font-bold text-yellow-600">
                    {overallStats.coursePassRate}%
                  </div>
                  <div className="text-sm text-yellow-800">Pass Rate</div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Quiz Results */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Target className="w-5 h-5" />
                Quiz Performance
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {Object.entries(quizResults).map(
                  ([weekKey, result]: [string, any]) => (
                    <div
                      key={weekKey}
                      className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                    >
                      <div className="flex items-center gap-2">
                        <CheckCircle className="w-4 h-4 text-green-500" />
                        <span className="font-medium text-black">
                          {weekKey.replace("week", "Week ")} Quiz
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span
                          className={`font-bold ${
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
                        <span
                          className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs ${
                            result.results.percentage > 40
                              ? "bg-green-100 text-green-800 border-green-300"
                              : "bg-red-100 text-red-800 border-red-300"
                          }`}
                        >
                          {result.results.grade_letter}
                        </span>
                      </div>
                    </div>
                  )
                )}
              </div>
            </CardContent>
          </Card>

          {/* Achievements */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Star className="w-5 h-5" />
                Achievements
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {overallStats.averageScore >= 90 && (
                  <div className="flex items-center gap-3 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                    <Star className="w-5 h-5 text-yellow-500" />
                    <div>
                      <div className="font-medium text-yellow-800">
                        Excellence Award
                      </div>
                      <div className="text-sm text-yellow-700">
                        90%+ average score
                      </div>
                    </div>
                  </div>
                )}

                {overallStats.coursePassRate === 100 && (
                  <div className="flex items-center gap-3 p-3 bg-green-50 border border-green-200 rounded-lg">
                    <Trophy className="w-5 h-5 text-green-500" />
                    <div>
                      <div className="font-medium text-green-800">
                        Perfect Completion
                      </div>
                      <div className="text-sm text-green-700">
                        Passed all quizzes
                      </div>
                    </div>
                  </div>
                )}

                {overallStats.highestScore === 100 && (
                  <div className="flex items-center gap-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                    <CheckCircle className="w-5 h-5 text-blue-500" />
                    <div>
                      <div className="font-medium text-blue-800">
                        Perfect Score
                      </div>
                      <div className="text-sm text-blue-700">
                        100% on at least one quiz
                      </div>
                    </div>
                  </div>
                )}

                <div className="flex items-center gap-3 p-3 bg-purple-50 border border-purple-200 rounded-lg">
                  <BookOpen className="w-5 h-5 text-purple-500" />
                  <div>
                    <div className="font-medium text-purple-800">
                      Course Completion
                    </div>
                    <div className="text-sm text-purple-700">
                      Completed all {overallStats.totalQuizzes} weeks
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Action Buttons */}
        <div className="mt-8 text-center space-y-4">
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button
              onClick={handleDownloadCertificate}
              className="bg-green-600 hover:bg-green-700"
              size="lg"
            >
              <Download className="w-4 h-4 mr-2" />
              Download Certificate
            </Button>
            <Button
              onClick={handleStartNewCourse}
              variant="outline"
              size="lg"
              className="bg-white text-blue-600 border-blue-600 hover:bg-blue-50"
            >
              <Home className="w-4 h-4 mr-2" />
              Start New Course
            </Button>
          </div>

          <p className="text-sm text-gray-600">
            Thank you for choosing our adaptive learning platform. Keep learning
            and growing! 🚀
          </p>
        </div>
      </div>
    </div>
  );
}

"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CheckCircle, Clock, AlertCircle } from "lucide-react";

interface Question {
  question_number: number;
  question_text: string;
  type: "multiple_choice" | "true_false" | "short_answer";
  options?: string[];
  correct_answer: string;
  explanation: string;
  points: number;
}

interface Quiz {
  quiz_id: string;
  week_number: number;
  week_title: string;
  questions: Question[];
  total_points: number;
  time_limit_minutes: number;
  completed?: boolean;
  results?: any;
}

interface QuizComponentProps {
  quiz: Quiz | null;
  weekInfo: any;
  courseContext: any;
  onQuizComplete: (results: any, adaptationSummary?: any) => void;
  onContinueToNextWeek?: () => void;
}

export default function QuizComponent({
  quiz,
  weekInfo,
  courseContext,
  onQuizComplete,
  onContinueToNextWeek,
}: QuizComponentProps) {
  const [quizSession, setQuizSession] = useState<any>(null);
  const [userAnswers, setUserAnswers] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [quizResults, setQuizResults] = useState<any>(null);
  const [timeRemaining, setTimeRemaining] = useState<number | null>(null);

  // Start Quiz
  const startQuiz = async () => {
    try {
      // Prepare proper week info with topics from lesson_topics
      const weekData = {
        week_number: weekInfo?.week_number || 1,
        title: weekInfo?.title || `Week ${weekInfo?.week_number || 1}`,
        topics: weekInfo?.lesson_topics?.map((lesson: any) => lesson.title) || [
          courseContext?.topic || "General topics",
        ],
      };

      console.log("Starting quiz with week data:", weekData);
      console.log("Course context:", courseContext);

      const response = await fetch("http://localhost:8000/create_quiz", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          week_info: weekData,
          course_context: courseContext,
        }),
      });

      const data = await response.json();
      if (data.success) {
        setQuizSession(data.quiz_session);
        setTimeRemaining(data.quiz_session.time_remaining);
        startTimer(data.quiz_session.time_remaining);
      }
    } catch (error) {
      console.error("Error starting quiz:", error);
    }
  };

  // Timer functionality
  const startTimer = (seconds: number) => {
    const timer = setInterval(() => {
      setTimeRemaining((prev) => {
        if (prev && prev <= 1) {
          clearInterval(timer);
          submitQuiz(); // Auto-submit when time runs out
          return 0;
        }
        return prev ? prev - 1 : 0;
      });
    }, 1000);
  };

  // Submit Quiz
  const submitQuiz = async () => {
    if (!quizSession) return;

    setIsSubmitting(true);
    try {
      const response = await fetch("http://localhost:8000/submit_quiz", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          quiz_session: quizSession,
          user_answers: userAnswers,
        }),
      });

      const data = await response.json();
      if (data.success) {
        const results = data.results || data.quiz_results;

        // Handle progressive content generation
        if (data.next_week_ready && results.percentage >= 70) {
          console.log("Next week content is being generated...");
          results.contentGenerationStatus = "generating";
          results.nextWeekReady = true;
        }

        // Handle adaptive learning feedback
        if (data.adaptation_summary) {
          console.log("Adaptive Learning Applied:", data.adaptation_summary);
          results.adaptationSummary = data.adaptation_summary;
        }

        setQuizResults(results);

        // Store quiz results in session storage
        const sessionResults = JSON.parse(
          sessionStorage.getItem("sessionQuizResults") || "{}"
        );
        sessionResults[`week${weekInfo?.week_number}`] = {
          results: results,
          completed_at: new Date().toISOString(),
          adaptationSummary: data.adaptation_summary,
        };
        sessionStorage.setItem(
          "sessionQuizResults",
          JSON.stringify(sessionResults)
        );

        onQuizComplete(results, data.adaptation_summary);
      }
    } catch (error) {
      console.error("Error submitting quiz:", error);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle answer selection
  const handleAnswerChange = (questionNumber: number, answer: string) => {
    setUserAnswers((prev) => ({
      ...prev,
      [questionNumber.toString()]: answer,
    }));
  };

  // Format time for display
  const formatTime = (seconds: number) => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds.toString().padStart(2, "0")}`;
  };

  // Determine if this is a final assessment (final week) or regular quiz
  const isFinalAssessment =
    weekInfo?.week_number >=
    (courseContext?.navigation?.total_weeks ||
      courseContext?.weeks?.length ||
      1);
  const assessmentType = isFinalAssessment ? "Final Assessment" : "Quiz";

  // Show quiz results
  if (quizResults) {
    return (
      <div className="space-y-4">
        <Card className="border-green-200 bg-green-50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-green-800">
              <CheckCircle className="w-5 h-5" />
              {assessmentType} Completed!
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="text-2xl font-bold text-green-600">
                  {quizResults.percentage}%
                </div>
                <div className="text-sm text-green-700">Final Score</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-blue-600">
                  {quizResults.correct_answers}
                </div>
                <div className="text-sm text-blue-700">Correct Answers</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-purple-600">
                  {quizResults.user_score}
                </div>
                <div className="text-sm text-purple-700">Points Earned</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-orange-600">
                  {quizResults.grade_letter}
                </div>
                <div className="text-sm text-orange-700">Grade</div>
              </div>
            </div>

            <div className="mt-4 p-3 rounded-lg">
              <h4 className="font-medium mb-2 text-black">Overall Feedback</h4>
              <p className="text-sm text-neutral-700">
                {quizResults.overall_feedback}
              </p>

              {/* Navigation guidance */}
              {quizResults.percentage > 40 ? (
                <div className="space-y-3">
                  <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
                    <p className="text-sm text-green-800">
                      🎉 <strong>Great work!</strong> You can continue to the
                      next week.{" "}
                      {(weekInfo?.week_number || 1) >=
                      (courseContext?.navigation?.total_weeks ||
                        courseContext?.weeks?.length ||
                        1) ? (
                        <span>
                          Use the <strong>"Complete Course 🎉"</strong> button
                          at the bottom to finish the course and see your
                          completion certificate!
                        </span>
                      ) : (
                        <span>
                          Use the{" "}
                          <strong>
                            "Continue to Week {(weekInfo?.week_number || 1) + 1}
                            "
                          </strong>{" "}
                          button at the bottom of the page to proceed to the
                          next week's overview and materials.
                        </span>
                      )}
                    </p>
                  </div>

                  {/* Progressive Content Generation Notification */}
                  {quizResults.nextWeekReady &&
                    quizResults.percentage >= 70 && (
                      <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                        <p className="text-sm text-blue-800 flex items-center gap-2">
                          <span className="animate-pulse">🚀</span>
                          <strong>Great news!</strong> Your performance has
                          unlocked Week {(weekInfo?.week_number || 1) + 1}! The
                          content has been automatically generated and
                          personalized based on your progress.
                        </p>
                      </div>
                    )}
                </div>
              ) : (
                <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg">
                  <p className="text-sm text-red-800">
                    📚 You need to score above 40% to continue. Please review
                    the material and retake the quiz when ready.
                  </p>
                </div>
              )}
            </div>

            {/* Adaptive Learning Summary */}
            {quizResults.adaptationSummary && (
              <div className="mt-4 p-4 bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg border border-blue-200">
                <h4 className="font-medium mb-2 text-blue-800 flex items-center gap-2">
                  🧠 Adaptive Learning Applied
                </h4>
                <div className="space-y-2 text-sm">
                  <div>
                    <span className="font-medium text-blue-700">
                      Your Performance:
                    </span>{" "}
                    <span
                      className={`font-bold ${
                        quizResults.adaptationSummary.performance >= 90
                          ? "text-green-600"
                          : quizResults.adaptationSummary.performance >= 70
                          ? "text-yellow-600"
                          : "text-red-600"
                      }`}
                    >
                      {quizResults.adaptationSummary.performance}%
                    </span>
                  </div>
                  <div>
                    <span className="font-medium text-blue-700">
                      Next Week Adaptation:
                    </span>{" "}
                    <span className="capitalize text-purple-600 font-medium">
                      {quizResults.adaptationSummary.adaptation_type}
                    </span>
                  </div>
                  <div className="mt-3 p-3 bg-white/70 rounded border-l-4 border-blue-400">
                    {quizResults.adaptationSummary.adaptation_type ===
                      "accelerated" && (
                      <div className="text-green-700">
                        <span className="font-medium">🚀 Excellent work!</span>{" "}
                        Week {quizResults.adaptationSummary.current_week + 1}{" "}
                        will be more challenging with advanced topics and harder
                        quiz questions.
                      </div>
                    )}
                    {quizResults.adaptationSummary.adaptation_type ===
                      "reinforced" && (
                      <div className="text-blue-700">
                        <span className="font-medium">
                          💪 Building strength!
                        </span>{" "}
                        Week {quizResults.adaptationSummary.current_week + 1}{" "}
                        will review challenging concepts with extra support and
                        practice.
                      </div>
                    )}
                    {quizResults.adaptationSummary.adaptation_type ===
                      "balanced" && (
                      <div className="text-purple-700">
                        <span className="font-medium">⚖️ Steady progress!</span>{" "}
                        Week {quizResults.adaptationSummary.current_week + 1}{" "}
                        will maintain current pace with balanced content.
                      </div>
                    )}
                  </div>
                  {quizResults.nextWeekPreview && (
                    <div className="mt-3 text-xs text-neutral-600">
                      <span className="font-medium">Next week preview:</span>{" "}
                      {quizResults.nextWeekPreview.title}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Question-by-question feedback */}
            <div className="mt-6 space-y-3">
              <h4 className="font-medium text-black">Question Review</h4>
              {quizResults.feedback?.map((questionFeedback: any) => (
                <Card
                  key={questionFeedback.question_number}
                  className={
                    questionFeedback.is_correct
                      ? "border-green-200"
                      : "border-red-200"
                  }
                >
                  <CardContent className="p-3">
                    <div className="flex items-start gap-2">
                      <div className="flex-shrink-0">
                        {questionFeedback.is_correct ? (
                          <CheckCircle className="w-4 h-4 text-green-500 mt-0.5" />
                        ) : (
                          <AlertCircle className="w-4 h-4 text-red-500 mt-0.5" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium mb-1 text-black">
                          Question {questionFeedback.question_number}
                        </div>
                        <div className="text-xs text-neutral-600 mb-2">
                          {questionFeedback.question_text}
                        </div>
                        <div className="text-xs">
                          <span className="text-neutral-500">
                            Your answer:{" "}
                          </span>
                          <span
                            className={
                              questionFeedback.is_correct
                                ? "text-green-600"
                                : "text-red-600"
                            }
                          >
                            {questionFeedback.user_answer || "No answer"}
                          </span>
                        </div>
                        {!questionFeedback.is_correct && (
                          <div className="text-xs mt-1">
                            <span className="text-neutral-500">
                              Correct answer:{" "}
                            </span>
                            <span className="text-green-600">
                              {questionFeedback.correct_answer}
                            </span>
                          </div>
                        )}
                        {questionFeedback.explanation && (
                          <div className="text-xs text-neutral-600 mt-2">
                            {questionFeedback.explanation}
                          </div>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Show active quiz
  if (quizSession && quizSession.quiz) {
    return (
      <div className="space-y-4">
        {/* Quiz Header */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Week {quizSession.quiz.week_number} Quiz</CardTitle>
              {timeRemaining !== null && (
                <div className="flex items-center gap-2">
                  <Clock className="w-4 h-4" />
                  <span
                    className={`font-mono ${
                      timeRemaining < 300 ? "text-red-600" : ""
                    }`}
                  >
                    {formatTime(timeRemaining)}
                  </span>
                </div>
              )}
            </div>
            <p className="text-sm text-neutral-600">
              {quizSession.quiz.questions?.length} questions •{" "}
              {quizSession.quiz.total_points} points
            </p>
          </CardHeader>
        </Card>

        {/* Quiz Questions */}
        <div className="space-y-4">
          {quizSession.quiz.questions?.map((question: Question) => (
            <Card key={question.question_number}>
              <CardContent className="p-4">
                <div className="space-y-3">
                  <div>
                    <h4 className="font-medium">
                      Question {question.question_number}
                      <span className="text-sm text-neutral-500 ml-2">
                        ({question.points}{" "}
                        {question.points === 1 ? "point" : "points"})
                      </span>
                    </h4>
                    <p className="text-sm text-white mt-1">
                      {question.question_text}
                    </p>
                  </div>

                  {/* Multiple Choice Only */}
                  {question.type === "multiple_choice" && question.options && (
                    <div className="space-y-2">
                      {["A", "B", "C", "D"].map((letter, index) => (
                        <label
                          key={letter}
                          className="flex items-center gap-2 cursor-pointer p-2 rounded-lg hover:bg-neutral-50 hover:text-black"
                        >
                          <input
                            type="radio"
                            name={`question_${question.question_number}`}
                            value={letter}
                            onChange={(e) =>
                              handleAnswerChange(
                                question.question_number,
                                e.target.value
                              )
                            }
                            className="w-4 h-4"
                          />
                          <span className="text-sm">
                            <span className="font-medium">{letter})</span>{" "}
                            {(question.options && question.options[index]) ||
                              `Option ${letter}`}
                          </span>
                        </label>
                      ))}
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Submit Button */}
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div className="text-sm text-white">
                Make sure all questions are answered before submitting.
              </div>
              <Button
                onClick={submitQuiz}
                disabled={isSubmitting}
                className="px-6"
              >
                {isSubmitting ? "Submitting..." : `Submit ${assessmentType}`}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Show quiz start screen
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          Week {weekInfo?.week_number} {assessmentType}
        </CardTitle>
        <p className="text-sm">
          {isFinalAssessment
            ? "Review the assessment guidelines and complete your final evaluation"
            : "Test your understanding of this week's material"}
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <div className="font-medium">Questions</div>
            <div>10 multiple choice</div>
          </div>
          <div>
            <div className="font-medium">Points</div>
            <div>20 points total</div>
          </div>
        </div>

        <div className="bg-neutral-50 p-3 rounded-lg text-sm">
          <h4 className="font-medium mb-1 text-black">Instructions:</h4>
          <ul className="text-neutral-600 space-y-1 text-xs">
            {isFinalAssessment ? (
              <>
                <li>
                  • This final assessment helps evaluate your overall
                  understanding
                </li>
                <li>
                  • Review each question carefully and select your best answer
                </li>
                <li>
                  • Use this as a learning opportunity to reinforce key concepts
                </li>
                <li>• Your responses will help determine course completion</li>
                <li>• Complete this final assessment to finish the course</li>
              </>
            ) : (
              <>
                <li>
                  • Select the best answer (A, B, C, or D) for each question
                </li>
                <li>• Each question is worth 2 points</li>
                <li>• You can review and change answers before submitting</li>
                <li>• The quiz will auto-submit when time runs out</li>
                <li>
                  • You need to complete this quiz to unlock the next week
                </li>
              </>
            )}
          </ul>
        </div>

        <Button onClick={startQuiz} className="w-full">
          Start {assessmentType}
        </Button>
      </CardContent>
    </Card>
  );
}

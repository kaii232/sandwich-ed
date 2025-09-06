"use client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function SyllabusViewer({
  syllabus,
  onStart,
}: {
  syllabus: string;
  onStart: () => void;
}) {
  if (!syllabus) return null;
  return (
    <div className="border rounded-xl p-4 space-y-4">
      <h3 className="text-lg font-semibold">Your Personalized Syllabus</h3>
      <div className="prose max-w-none">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{syllabus}</ReactMarkdown>
      </div>
      <button
        onClick={onStart}
        className="px-4 py-2 rounded-lg bg-green-600 text-white"
      >
        Start Course
      </button>
    </div>
  );
}

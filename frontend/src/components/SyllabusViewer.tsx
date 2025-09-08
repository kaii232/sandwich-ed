"use client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import StartLessonButton from "./StartLessonButton";

export default function SyllabusViewer({
  syllabus,
  chatState,
}: {
  syllabus: string;
  chatState: any;
}) {
  if (!syllabus) return null;
  return (
    <div className="border rounded-xl p-4 space-y-4">
      <h3 className="text-lg font-semibold">Your Personalised Syllabus</h3>
      <div className="prose max-w-none">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{syllabus}</ReactMarkdown>
      </div>
      <StartLessonButton syllabus={syllabus} chatState={chatState} />
    </div>
  );
}

"use client";
import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import StartLessonButton from "./StartLessonButton";

// keep ids on headings so the outer "Jump to..." can scroll to them
function slugify(s: string) {
  return s
    .toLowerCase()
    .replace(/[^\w\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-");
}

export default function SyllabusViewer({
  syllabus,
  chatState,
}: {
  syllabus: string;
  chatState: any;
}) {
  if (!syllabus) return null;

  const components = {
    h2: (props: any) => {
      const text = String(props.children ?? "");
      return (
        <h2 id={slugify(text)} className="scroll-mt-16">
          {props.children}
        </h2>
      );
    },
    h3: (props: any) => {
      const text = String(props.children ?? "");
      return (
        <h3 id={slugify(text)} className="scroll-mt-16">
          {props.children}
        </h3>
      );
    },
    table: (props: any) => (
      <div className="overflow-x-auto -mx-1">
        <table className="min-w-[560px]" {...props} />
      </div>
    ),
  };

  return (
    <div>
      <div className="prose prose-sm max-w-none leading-6 [&_:where(h1,h2,h3)]:mt-5 [&_:where(h1,h2,h3)]:mb-2 [&_ul]:my-3 [&_ol]:my-3">
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
          {syllabus}
        </ReactMarkdown>
      </div>

      <div className="mt-4">
        <StartLessonButton syllabus={syllabus} chatState={chatState} />
      </div>
    </div>
  );
}

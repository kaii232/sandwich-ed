"use client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function WeekViewer({ week }: { week: any }) {
  if (!week) return null;
  return (
    <div className="border rounded-xl p-4 space-y-4">
      <h3 className="text-lg font-semibold">{week.title ?? "Week"}</h3>
      <div className="prose max-w-none">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {week.content ?? "_No content available_"}
        </ReactMarkdown>
      </div>
      {Array.isArray(week.videos) && week.videos.length > 0 && (
        <div>
          <h4 className="font-medium mb-2">Suggested Videos</h4>
          <ul className="list-disc pl-5">
            {week.videos.map((v: any, i: number) => (
              <li key={i}>
                <a
                  className="underline"
                  href={v.url}
                  target="_blank"
                  rel="noreferrer"
                >
                  {v.title || v.url}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

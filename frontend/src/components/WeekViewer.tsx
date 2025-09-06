"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export type Lesson = {
  id: string;
  title: string;
  summary: string;
  expandable: boolean;
  loaded?: boolean;
  lesson_info: Record<string, any>;
  content?: string;
  videos?: {
    title?: string | null;
    channel?: string | null;
    url: string;
    description?: string | null;
    thumbnail?: string | null;
    published?: string | null;
    is_search?: boolean;
  }[];
};

export default function WeekViewer({
  week,
  onLoadLesson,
}: {
  week: any;
  onLoadLesson?: (info: any) => Promise<any | null>;
}) {
  const [openId, setOpenId] = useState<string | null>(null);
  const [lessonMap, setLessonMap] = useState<Record<string, Lesson>>({});
  if (!week)
    return (
      <div className="text-sm text-neutral-600">
        Select a week to get started.
      </div>
    );

  const lessons: Lesson[] = week?.lesson_content || [];

  async function toggle(id: string, info: any) {
    setOpenId((prev) => (prev === id ? null : id));
    // Lazy load
    if (!lessonMap[id] && onLoadLesson) {
      const loaded = await onLoadLesson(info);
      if (loaded) {
        setLessonMap((m) => ({
          ...m,
          [id]: {
            id,
            title: info.title,
            summary: info.summary,
            expandable: true,
            lesson_info: info,
            ...loaded,
          },
        }));
      }
    }
  }

  return (
    <div className="space-y-6">
      <section>
        <h2 className="text-xl font-semibold mb-2">{week.title}</h2>
        <article
          className="prose prose-neutral max-w-none"
          dangerouslySetInnerHTML={{ __html: mdToHtml(week.overview || "") }}
        />
      </section>

      <section className="space-y-3">
        <h3 className="text-lg font-semibold">Lessons</h3>
        {lessons.length === 0 && (
          <div className="text-sm text-neutral-600">
            No lessons for this week.
          </div>
        )}
        {lessons.map((ls: any) => {
          const isOpen = openId === ls.id;
          const loaded = lessonMap[ls.id];
          return (
            <Card key={ls.id} className="rounded-xl">
              <CardHeader className="flex flex-row items-center justify-between gap-2">
                <CardTitle className="text-base">{ls.title}</CardTitle>
                <Button variant="outline" onClick={() => toggle(ls.id, ls)}>
                  {isOpen ? "Collapse" : "Expand"}
                </Button>
              </CardHeader>
              {isOpen && (
                <CardContent className="space-y-3">
                  <p className="text-sm text-neutral-700">{ls.summary}</p>
                  <div
                    className="prose prose-neutral max-w-none"
                    dangerouslySetInnerHTML={{
                      __html: mdToHtml(loaded?.content || "Loading…"),
                    }}
                  />
                  {loaded?.videos?.length ? (
                    <div className="grid sm:grid-cols-2 gap-3">
                      {loaded.videos.map((v: any, i: number) => (
                        <a
                          key={i}
                          href={v.url}
                          target="_blank"
                          className="block rounded-lg border p-3 hover:bg-neutral-50"
                        >
                          <div className="text-sm font-medium line-clamp-2">
                            {v.title || "Search results"}
                          </div>
                          <div className="text-xs text-neutral-600">
                            {v.channel || "YouTube"}
                          </div>
                          {v.description && (
                            <p className="text-xs mt-1 line-clamp-2">
                              {v.description}
                            </p>
                          )}
                        </a>
                      ))}
                    </div>
                  ) : null}
                </CardContent>
              )}
            </Card>
          );
        })}
      </section>

      <section className="space-y-2">
        <h3 className="text-lg font-semibold">Activities & Resources</h3>
        <article
          className="prose prose-neutral max-w-none"
          dangerouslySetInnerHTML={{ __html: mdToHtml(week.activities || "") }}
        />
      </section>
    </div>
  );
}

// Tiny markdown-to-HTML helper (very small subset)
function mdToHtml(md: string) {
  return md
    .replace(/^###\s(.+)$/gm, "<h3>$1</h3>")
    .replace(/^##\s(.+)$/gm, "<h2>$1</h2>")
    .replace(/^#\s(.+)$/gm, "<h1>$1</h1>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/^\-\s(.+)$/gm, "<li>$1</li>")
    .replace(/\n\n/g, "<br/><br/>")
    .replace(/^(?:(?:<li>.*<\/li>\n?)+)$/gms, "<ul>$&</ul>");
}

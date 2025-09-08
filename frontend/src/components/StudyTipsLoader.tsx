"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import Image from "next/image";

type StudyTipsLoaderProps = {
  open: boolean;
  weekInfo: any | null;
  courseContext: any | null;
  performance?: any | null; // e.g. { lastQuiz: { percentage: 72 }, overallProgress: 25 }
  iconSrc?: string; // e.g. "/logo/sandwiched.svg"
};

const FALLBACK_TIPS: string[] = [
  "Study in short sprints (25–30 min) and take 5-min breaks.",
  "Explain the concept out loud as if teaching a friend.",
  "Mix practice: alternate easy/medium questions to build momentum.",
  "Use spaced repetition: review tough items again tomorrow.",
  "Write a mini-summary after each section using your own words.",
  "Sleep > cram: memory consolidates best after rest.",
];

export default function StudyTipsLoader({
  open,
  weekInfo,
  courseContext,
  performance,
  iconSrc = "/logo/sandwiched.svg",
}: StudyTipsLoaderProps) {
  const [tips, setTips] = useState<string[]>([]);
  const [i, setI] = useState(0);
  const started = useRef(false);

  // rotate tips every 3s while open
  useEffect(() => {
    if (!open) return;
    const id = setInterval(() => setI((x) => x + 1), 3000);
    return () => clearInterval(id);
  }, [open]);

  // fetch tips from /api/study-tips (proxy to backend)
  useEffect(() => {
    if (!open) return;
    // don’t refetch multiple times during the same loading window
    if (started.current) return;
    started.current = true;

    const ac = new AbortController();
    (async () => {
      try {
        const res = await fetch("/api/study-tips", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            week_info: weekInfo ?? {},
            course_context: courseContext ?? {},
            student_performance: performance ?? null,
          }),
          signal: ac.signal,
        });
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data) && data.length) setTips(data.slice(0, 12));
        }
      } catch {
        /* ignore; fall back below */
      }
    })();

    return () => {
      ac.abort();
      started.current = false;
    };
  }, [open, weekInfo, courseContext, performance]);

  const activeTips = useMemo(
    () => (tips.length ? tips : FALLBACK_TIPS),
    [tips]
  );
  const tip =
    activeTips[
      ((i % activeTips.length) + activeTips.length) % activeTips.length
    ];

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[90] bg-neutral-900/70 backdrop-blur-sm flex items-center justify-center p-6"
      role="dialog"
      aria-modal="true"
      aria-busy="true"
    >
      <div className="w-full max-w-lg rounded-2xl border bg-white shadow-xl">
        {/* header */}
        <div className="p-6 flex items-center gap-4">
          <div className="shrink-0 rounded-xl border p-2 bg-white">
            <Image
              src="/sandwich-ed.png"
              alt="Sandwich-ed"
              width={56}
              height={56}
              priority
            />
          </div>
          <div className="min-w-0">
            <h2 className="text-lg font-semibold leading-tight text-black">
              Preparing your lesson…
            </h2>
            <p className="text-sm text-neutral-600">
              Generating content and micro-interventions tailored to you.
            </p>
          </div>
        </div>

        {/* progress shimmer */}
        <div className="px-6">
          <div className="h-2 w-full overflow-hidden rounded-full bg-neutral-100">
            <div className="h-2 w-1/3 animate-pulse rounded-full bg-[#D7CCFF]" />
          </div>
        </div>

        {/* tip card */}
        <div className="p-6">
          <div className="rounded-xl border bg-neutral-50 p-4">
            <div className="text-[11px] font-medium uppercase tracking-wide text-neutral-500">
              Study tip
            </div>
            <div className="mt-1 text-sm leading-relaxed text-black">{tip}</div>
          </div>

          {/* small print */}
          <div className="mt-3 text-xs text-neutral-500">
            You can keep this tab open—your personalized content will appear
            automatically.
          </div>
        </div>
      </div>
    </div>
  );
}

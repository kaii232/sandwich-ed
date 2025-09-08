"use client";
import { useEffect, useState } from "react";

type Result = {
  risk: "low" | "watch" | "elevated" | "urgent";
  message: string;
  show_resources?: boolean;
};

type Props = {
  /** show after these checkpoint counts, e.g., [1, 2] for “after 1st and 2nd” */
  triggerAt?: number[];
  /** OR: show every N checkpoints (ignored if triggerAt provided) */
  every?: number;
  /** cooldown checkpoints after showing once (prevents immediate re-show) */
  cooldown?: number;
};

export default function WellbeingCheck({
  triggerAt = [1, 2],
  every,
  cooldown = 1,
}: Props) {
  const [open, setOpen] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [mood, setMood] = useState<number>(3);
  const [phq2, setPhq2] = useState<[number, number]>([0, 0]);
  const [gad2, setGad2] = useState<[number, number]>([0, 0]);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);

  // checkpoint gating state
  const LAST_SHOWN_KEY = "wb_last_shown_cp"; // last checkpoint count we displayed at
  const COUNT_KEY = "wb_cp_count";

  useEffect(() => {
    function onCheckpoint(e: any) {
      const count = Number(
        e?.detail?.count ?? localStorage.getItem(COUNT_KEY) ?? 0
      );
      const lastShown = Number(localStorage.getItem(LAST_SHOWN_KEY) || 0);

      // prevent immediate repeats via cooldown
      if (cooldown > 0 && count - lastShown < cooldown) return;

      // trigger logic: explicit list beats "every"
      const shouldOpen = triggerAt?.length
        ? triggerAt.includes(count)
        : every && count > 0 && count % every === 0;

      if (shouldOpen) setOpen(true);
    }

    window.addEventListener("wb:checkpoint", onCheckpoint as EventListener);
    return () =>
      window.removeEventListener(
        "wb:checkpoint",
        onCheckpoint as EventListener
      );
  }, [triggerAt, every, cooldown]);

  async function submit() {
    setSending(true);
    try {
      const r = await fetch("/api/wellbeing/check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mood,
          phq2,
          gad2,
          free_text: text || undefined,
        }),
      });
      const data = await r.json();
      setResult(data);
      // mark last shown at the current count
      const count = Number(localStorage.getItem(COUNT_KEY) || 0);
      localStorage.setItem(LAST_SHOWN_KEY, String(count));
    } finally {
      setSending(false);
    }
  }

  function closeAll() {
    setOpen(false);
    setResult(null);
    // also mark last shown so we don’t reopen immediately
    const count = Number(localStorage.getItem(COUNT_KEY) || 0);
    localStorage.setItem(LAST_SHOWN_KEY, String(count));
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/30">
      <div className="w-[520px] max-w-[92vw] rounded-2xl bg-white shadow-xl p-5">
        <h3 className="text-lg font-semibold mb-2">Quick wellbeing check</h3>

        {!result ? (
          <div className="space-y-4">
            <p className="text-sm text-neutral-600">
              Totally optional. Your responses just help us pace your learning.
            </p>

            {/* Mood */}
            <div>
              <label className="text-sm font-medium">
                How’s your mood today?
              </label>
              <div className="mt-2 flex gap-1.5">
                {[1, 2, 3, 4, 5].map((n) => (
                  <button
                    key={n}
                    onClick={() => setMood(n)}
                    className={`px-3 py-1.5 rounded border ${
                      mood === n ? "bg-black text-white" : "bg-white"
                    }`}
                  >
                    {n}
                  </button>
                ))}
              </div>
            </div>

            {/* PHQ-2 / GAD-2 */}
            <div className="text-sm">
              <div className="font-medium mb-1">In the last 2 weeks…</div>
              <div className="grid grid-cols-1 gap-2">
                <div>
                  <div>Little interest or pleasure in doing things</div>
                  <select
                    className="mt-1 border rounded px-2 py-1"
                    value={phq2[0]}
                    onChange={(e) => setPhq2([Number(e.target.value), phq2[1]])}
                  >
                    {[
                      "0 Not at all",
                      "1 Several days",
                      "2 > Half the days",
                      "3 Nearly every day",
                    ].map((t, i) => (
                      <option key={i} value={i}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <div>Feeling down, depressed, or hopeless</div>
                  <select
                    className="mt-1 border rounded px-2 py-1"
                    value={phq2[1]}
                    onChange={(e) => setPhq2([phq2[0], Number(e.target.value)])}
                  >
                    {[
                      "0 Not at all",
                      "1 Several days",
                      "2 > Half the days",
                      "3 Nearly every day",
                    ].map((t, i) => (
                      <option key={i} value={i}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="mt-2">
                  <div>Feeling nervous, anxious, or on edge</div>
                  <select
                    className="mt-1 border rounded px-2 py-1"
                    value={gad2[0]}
                    onChange={(e) => setGad2([Number(e.target.value), gad2[1]])}
                  >
                    {[
                      "0 Not at all",
                      "1 Several days",
                      "2 > Half the days",
                      "3 Nearly every day",
                    ].map((t, i) => (
                      <option key={i} value={i}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <div>Not being able to stop/control worrying</div>
                  <select
                    className="mt-1 border rounded px-2 py-1"
                    value={gad2[1]}
                    onChange={(e) => setGad2([gad2[0], Number(e.target.value)])}
                  >
                    {[
                      "0 Not at all",
                      "1 Several days",
                      "2 > Half the days",
                      "3 Nearly every day",
                    ].map((t, i) => (
                      <option key={i} value={i}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            {/* Free text */}
            <div>
              <label className="text-sm font-medium">
                Anything else you’d like to share? (optional)
              </label>
              <textarea
                className="mt-1 w-full h-20 border rounded p-2 text-sm"
                value={text}
                onChange={(e) => setText(e.target.value)}
              />
            </div>

            <div className="flex gap-2 justify-end">
              <button className="px-3 py-1.5 rounded border" onClick={closeAll}>
                Skip
              </button>
              <button
                className="px-3 py-1.5 rounded bg-black text-white"
                onClick={submit}
                disabled={sending}
              >
                {sending ? "Submitting…" : "Submit"}
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="text-sm whitespace-pre-wrap">{result.message}</div>
            {result.show_resources && (
              <div className="text-xs text-neutral-600">
                If you’re in immediate danger, contact local emergency services.
                You can also reach out to a trusted person or a licensed
                professional/counsellor in your area.
              </div>
            )}
            <div className="flex gap-2 justify-end">
              <button
                className="px-3 py-1.5 rounded bg-black text-white"
                onClick={closeAll}
              >
                Close
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

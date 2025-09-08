"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { MessageCircle, X, Send } from "lucide-react";

type ChatMsg = { role: "user" | "assistant"; content: string };

export default function LessonChatbot(props: {
  courseContext: any;
  weekContext: any;
}) {
  const { courseContext, weekContext } = props;
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<ChatMsg[]>([
    { role: "assistant", content: "Hi! Ask me anything about this lesson. 😊" },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) {
      boxRef.current?.scrollTo({
        top: boxRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [open, msgs, loading]);

  async function send() {
    const q = input.trim();
    if (!q || loading) return;
    setInput("");
    setMsgs((m) => [...m, { role: "user", content: q }]);
    setLoading(true);
    try {
      const res = await fetch("/api/lesson_chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: q,
          history: msgs,
          course_context: courseContext,
          week_context: weekContext,
        }),
      });
      const data = await res.json();
      setMsgs((m) => [
        ...m,
        {
          role: "assistant",
          content: data.answer || "Hmm, try rephrasing your question.",
        },
      ]);
    } catch (e) {
      setMsgs((m) => [
        ...m,
        {
          role: "assistant",
          content: "I ran into an error. Please try again.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      {/* Floating Action Button */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="fixed bottom-4 right-4 z-40 rounded-full p-4 shadow-lg bg-black text-white hover:opacity-90"
        aria-label="Open lesson tutor"
      >
        {open ? (
          <X className="w-8 h-8" />
        ) : (
          <img src="/sandwich-ed.png" className="w-8 h-8 object-fill" />
        )}
      </button>

      {/* Chat Panel */}
      {open && (
        <div className="fixed bottom-24 right-4 z-40 w-[360px] max-h-[70vh] rounded-2xl border bg-white shadow-xl flex flex-col">
          <div className="px-4 py-3 border-b font-medium text-black">
            Lesson Tutor
          </div>
          <div
            ref={boxRef}
            className="flex-1 overflow-y-auto p-3 space-y-2 text-sm"
          >
            {msgs.map((m, i) => (
              <div
                key={i}
                className={m.role === "user" ? "text-right" : "text-left"}
              >
                <div
                  className={
                    "inline-block rounded-2xl px-3 py-2 " +
                    (m.role === "user"
                      ? "bg-blue-600 text-white"
                      : "bg-blue-200 text-black")
                  }
                >
                  {m.content}
                </div>
              </div>
            ))}
            {loading && (
              <div className="text-xs text-neutral-500">Thinking…</div>
            )}
          </div>
          <div className="p-3 border-t flex gap-2">
            <input
              className="flex-1 border rounded-lg px-3 py-2 text-sm text-black"
              placeholder="Ask about this lesson/quiz/resources…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send()}
              disabled={loading}
            />
            <button
              onClick={send}
              className="px-3 py-2 rounded-lg bg-black text-white disabled:opacity-60"
              disabled={loading}
              aria-label="Send"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </>
  );
}

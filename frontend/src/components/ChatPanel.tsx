"use client";
import { useEffect, useRef, useState } from "react";
import { chatbotStep, ChatResp, ChatState } from "@/lib/api";
import SyllabusViewer from "@/components/SyllabusViewer";

type Msg = { role: "bot" | "user"; text: string };

export default function ChatPanel(props: {
  onSyllabus: (syllabus: string, state: ChatState) => void;
  onState: (state: ChatState) => void;
}) {
  const [state, setState] = useState<ChatState>({});
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const [syllabus, setSyllabus] = useState<string>("");

  // Mobile drawer toggle for syllabus
  const [drawerOpen, setDrawerOpen] = useState(false);

  const listRef = useRef<HTMLDivElement>(null);

  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const resp: ChatResp = await chatbotStep({});
        setState(resp.state);
        props.onState(resp.state);
        setMsgs([{ role: "bot", text: resp.bot }]);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    // autoscroll chat list only
    listRef.current?.scrollTo({
      top: listRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [msgs, loading]);

  async function send(textOverride?: string) {
    if (loading) return;
    const text = (textOverride ?? input).trim();
    if (!text) return;
    if (!textOverride) setInput("");

    setMsgs((prev) => [...prev, { role: "user", text }]);
    setLoading(true);
    try {
      const resp = await chatbotStep(state, text);
      setState(resp.state);
      props.onState(resp.state);
      setMsgs((prev) => [...prev, { role: "bot", text: resp.bot }]);

      if (resp.syllabus) {
        setSyllabus(resp.syllabus);
        props.onSyllabus(resp.syllabus, resp.state);
        // keep the drawer closed on desktop; user opens it on mobile when needed
      }
    } catch {
      setMsgs((prev) => [
        ...prev,
        { role: "bot", text: "Something went wrong. Try again." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  // focus on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // re-focus whenever a send finishes
  useEffect(() => {
    if (!loading) inputRef.current?.focus();
  }, [loading]);

  function QuickReplies() {
    const step = (state as any)?.step as string | undefined;

    if (step === "difficulty") {
      return (
        <div className="mt-3 flex flex-wrap gap-2">
          {["Beginner", "Intermediate", "Advanced"].map((lvl) => (
            <button
              key={lvl}
              onClick={() => send(lvl)}
              disabled={loading}
              className="px-3 py-1.5 rounded-md border hover:bg-white hover:text-black disabled:opacity-60"
              title={`Select ${lvl}`}
            >
              {lvl}
            </button>
          ))}
        </div>
      );
    }

    if (step === "duration") {
      const presets = [
        "2 weeks",
        "4 weeks",
        "8 weeks",
        "1 hour/day for 4 weeks",
        "Weekend sprint",
      ];
      return (
        <div className="mt-3 flex flex-wrap gap-2">
          {presets.map((p) => (
            <button
              key={p}
              onClick={() => send(p)}
              disabled={loading}
              className="px-3 py-1.5 rounded-md border hover:bg-white hover:text-black disabled:opacity-60"
              title={p}
            >
              {p}
            </button>
          ))}
        </div>
      );
    }

    if (step === "confirmation") {
      return (
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            onClick={() => send("yes")}
            disabled={loading}
            className="px-3 py-1.5 rounded-md border hover:bg-white hover:text-black disabled:opacity-60"
            title="Generate my course now"
          >
            Yes, generate
          </button>
          <button
            onClick={() => send("modify")}
            disabled={loading}
            className="px-3 py-1.5 rounded-md border hover:bg-white hover:text-black disabled:opacity-60"
            title="I want to change something first"
          >
            Modify
          </button>
        </div>
      );
    }

    return null;
  }

  const placeholder =
    (state as any)?.step === "difficulty"
      ? "…or pick a level below"
      : (state as any)?.step === "confirmation"
      ? "…or use the buttons below"
      : syllabus
      ? "Type tweaks like: make it more project-based…"
      : "Tell the tutor what you want to learn…";

  return (
    <div className="border rounded-xl h-[72vh] flex flex-col overflow-hidden">
      {/* Pretty scrollbars for the two internal scrollers only */}
      <style jsx global>{`
        .nice-scrollbar {
          scrollbar-width: thin;
          scrollbar-color: #c7c7c7 transparent;
        }
        .nice-scrollbar::-webkit-scrollbar {
          width: 10px;
          height: 10px;
        }
        .nice-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .nice-scrollbar::-webkit-scrollbar-thumb {
          background: #c7c7c7;
          border-radius: 999px;
          border: 2px solid transparent;
          background-clip: padding-box;
        }
        .nice-scrollbar::-webkit-scrollbar-thumb:hover {
          background: #b3b3b3;
          background-clip: padding-box;
        }
      `}</style>

      {/* Header */}
      <div className="flex items-center justify-between gap-3 p-4 pb-3 border-b">
        <div className="font-semibold">Tutor Chat</div>
        {syllabus ? (
          <button
            type="button"
            className="md:hidden text-sm rounded-md border px-3 py-1.5"
            onClick={() => setDrawerOpen(true)}
            title="Open syllabus"
          >
            Syllabus
          </button>
        ) : null}
      </div>

      {/* Content: two columns (only this row grows) */}
      <div className="flex-1 overflow-hidden grid md:grid-cols-[1fr_380px] gap-4 p-4">
        {/* LEFT: Chat column (single scroll area) */}
        <div className="flex flex-col min-h-0">
          <div
            ref={listRef}
            className="flex-1 overflow-y-auto nice-scrollbar space-y-3 pr-1"
          >
            {msgs.map((m, i) => (
              <div key={i} className="border-b last:border-0 pb-2">
                <span className="font-semibold">
                  {m.role === "bot" ? "Tutor" : "You"}:{" "}
                </span>
                <span className="whitespace-pre-wrap">{m.text}</span>
              </div>
            ))}
            {loading && <div className="text-sm text-gray-500">Typing…</div>}

            {/* Quick replies */}
            <QuickReplies />
          </div>

          {/* Input row (pinned at bottom of left column) */}
          <div className="pt-3 border-t mt-3 flex gap-2">
            <input
              ref={inputRef}
              className="flex-1 border rounded-lg px-3 py-2"
              placeholder={placeholder}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send()}
              disabled={loading}
            />

            <button
              onClick={() => send()}
              disabled={loading}
              className="px-4 py-2 rounded-lg bg-[#D7CCFF] text-black disabled:opacity-60"
            >
              Send
            </button>
          </div>
        </div>

        {/* RIGHT: Docked syllabus (desktop only; single scroll area inside) */}
        <aside className="hidden md:flex flex-col min-h-0">
          <div className="rounded-lg border bg-white/30 flex flex-col overflow-hidden">
            <div className="flex items-center justify-between gap-2 p-3 border-b">
              <div className="text-md font-medium">Your Syllabus</div>
              <div className="flex gap-2">
                <button
                  className="px-3 py-1.5 rounded-md border"
                  onClick={() => send("regenerate")}
                  title="Regenerate with same settings"
                >
                  Regenerate
                </button>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto nice-scrollbar p-3">
              {syllabus ? (
                <SyllabusViewer syllabus={syllabus} chatState={state} />
              ) : (
                <div className="text-sm text-white">
                  The syllabus will appear here once generated.
                </div>
              )}
            </div>
          </div>
        </aside>
      </div>

      {/* MOBILE: Syllabus drawer (replaces inline preview to avoid duplicate scroll) */}
      {syllabus && drawerOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => setDrawerOpen(false)}
          />
          <div className="absolute inset-x-0 bottom-0 h-[80vh] bg-white rounded-t-2xl shadow-xl flex flex-col text-black">
            <div className="flex items-center justify-between gap-2 p-3 border-b">
              <div className="text-sm font-medium">Your Syllabus</div>
              <div className="flex gap-2">
                <button
                  className="px-3 py-1.5 rounded-md border"
                  onClick={() => send("regenerate")}
                  title="Regenerate with same settings"
                >
                  Regenerate
                </button>
                <button
                  className="px-3 py-1.5 rounded-md border"
                  onClick={() => setDrawerOpen(false)}
                >
                  Close
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto nice-scrollbar p-3">
              <SyllabusViewer syllabus={syllabus} chatState={state} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

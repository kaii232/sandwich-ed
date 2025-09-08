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

  // syllabus + inline editing
  const [syllabus, setSyllabus] = useState<string>("");
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");

  const listRef = useRef<HTMLDivElement>(null);

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
    // autoscroll whenever messages/loading/editing/syllabus change
    listRef.current?.scrollTo({
      top: listRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [msgs, loading, editing, syllabus, state]);

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
        setEditing(false);
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

  // Quick-reply button rows for specific steps
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

    // Step: duration — helpful presets users can click
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
    <div className="border rounded-xl p-4 flex flex-col">
      {/* Scrollable chat messages */}
      <div
        className="max-h-[360px] overflow-y-auto space-y-3 pr-1"
        ref={listRef}
      >
        {msgs.map((m, i) => (
          <div key={i}>
            <span className="font-semibold">
              {m.role === "bot" ? "Tutor" : "You"}:{" "}
            </span>
            <span className="whitespace-pre-wrap">{m.text}</span>
          </div>
        ))}
        {loading && <div className="text-sm text-gray-500">Typing…</div>}

        {/* Quick replies directly under the latest bot message */}
        <QuickReplies />

        {/* Syllabus area (appears only when available) — BEFORE the textbox */}
        {syllabus && !editing && (
          <div className="mt-4 space-y-3">
            <div className="flex gap-2 flex-wrap">
              <button
                className="px-3 py-1.5 rounded-md border"
                onClick={() => {
                  setDraft(syllabus);
                  setEditing(true);
                }}
                title="Edit the Markdown directly"
              >
                Edit syllabus
              </button>
              <button
                className="px-3 py-1.5 rounded-md border"
                onClick={() => send("regenerate")}
                title="Regenerate with the same settings (type tweaks above if needed)"
              >
                Regenerate
              </button>
            </div>

            <SyllabusViewer syllabus={syllabus} chatState={state} />
          </div>
        )}

        {/* Inline editor */}
        {syllabus && editing && (
          <div className="mt-4 space-y-2">
            <label className="text-sm font-medium">
              Edit syllabus (Markdown)
            </label>
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              className="w-full h-56 border rounded-lg p-3 font-mono text-sm"
            />
            <div className="flex gap-2">
              <button
                className="px-3 py-1.5 rounded-md bg-black text-white"
                onClick={() => {
                  setSyllabus(draft);
                  props.onSyllabus(draft, state);
                  setEditing(false);
                }}
              >
                Save
              </button>
              <button
                className="px-3 py-1.5 rounded-md border"
                onClick={() => setEditing(false)}
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Textbox row (moved AFTER syllabus area) */}
      <div className="mt-3 flex gap-2">
        <input
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
          className="px-4 py-2 rounded-lg bg-black text-white disabled:opacity-60"
        >
          Send
        </button>
      </div>
    </div>
  );
}

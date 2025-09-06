"use client";
import { useEffect, useRef, useState } from "react";
import { chatbotStep, ChatResp, ChatState } from "@/lib/api";

type Msg = { role: "bot" | "user"; text: string };

export default function ChatPanel(props: {
  onSyllabus: (syllabus: string, state: ChatState) => void;
  onState: (state: ChatState) => void;
}) {
  const [state, setState] = useState<ChatState>({});
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
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
    listRef.current?.scrollTo({
      top: listRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [msgs, loading]);

  async function send() {
    if (!input.trim() || loading) return;
    const text = input.trim();
    setMsgs((prev) => [...prev, { role: "user", text }]);
    setInput("");
    setLoading(true);
    try {
      const resp = await chatbotStep(state, text);
      setState(resp.state);
      props.onState(resp.state);
      setMsgs((prev) => [...prev, { role: "bot", text: resp.bot }]);
      if (resp.syllabus) props.onSyllabus(resp.syllabus, resp.state);
    } catch {
      setMsgs((prev) => [
        ...prev,
        { role: "bot", text: "Something went wrong. Try again." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="border rounded-xl p-4 flex flex-col h-[480px]">
      <div ref={listRef} className="flex-1 overflow-y-auto space-y-3 pr-1">
        {msgs.map((m, i) => (
          <div key={i}>
            <span className="font-semibold">
              {m.role === "bot" ? "Tutor" : "You"}:{" "}
            </span>
            <span className="whitespace-pre-wrap">{m.text}</span>
          </div>
        ))}
        {loading && <div className="text-sm text-gray-500">Typing…</div>}
      </div>
      <div className="mt-3 flex gap-2">
        <input
          className="flex-1 border rounded-lg px-3 py-2"
          placeholder="Tell the tutor what you want to learn…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
        />
        <button
          onClick={send}
          className="px-4 py-2 rounded-lg bg-black text-white"
        >
          Send
        </button>
      </div>
    </div>
  );
}

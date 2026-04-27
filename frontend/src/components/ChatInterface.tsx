"use client";

import { useState, useRef, useEffect } from "react";
import { Send, TrendingUp, IndianRupee, BarChart2, ArrowLeftRight, Sparkles } from "lucide-react";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface ChatInterfaceProps {
  activeThreadId: string | null;
  onCreateThread: () => Promise<string | null>;
  onThreadUpdated: () => Promise<void>;
  onSaveTitle: (threadId: string, title: string) => void;
}

// ── Groww logo mark (matches real Groww branding) ───────────────────────────
const GrowwLogoMark = ({ size = 36 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="growwBgCenter" x1="40" y1="0" x2="0" y2="40" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#6B6FF0" />
        <stop offset="50%" stopColor="#5059D6" />
        <stop offset="100%" stopColor="#00C896" />
      </linearGradient>
      <clipPath id="growwCircleCenter">
        <circle cx="20" cy="20" r="20" />
      </clipPath>
    </defs>
    <circle cx="20" cy="20" r="20" fill="url(#growwBgCenter)" />
    <g clipPath="url(#growwCircleCenter)">
      <path d="M-2 37 L5 26 L10 31 L18 19 L23 25 L31 14 L37 20 L44 13 L44 44 L-2 44 Z" fill="white" />
      <path d="M-2 32 L5 21 L10 26 L18 14 L23 20 L31 9 L37 15 L44 8 L44 38 L-2 40 Z" fill="white" opacity="0.55" />
      <path d="M-2 27 L5 16 L10 21 L18 9 L23 15 L31 4 L37 10 L44 3 L44 32 L-2 34 Z" fill="white" opacity="0.25" />
    </g>
  </svg>
);

// ── Preselected questions ────────────────────────────────────────────────────
const QUESTIONS = [
  {
    Icon: TrendingUp,
    question: "What is the NAV of Parag Parikh Flexi Cap Fund?",
  },
  {
    Icon: IndianRupee,
    question: "What is the expense ratio of Parag Parikh Large Cap Fund?",
  },
  {
    Icon: BarChart2,
    question: "What is the minimum SIP for Parag Parikh ELSS Tax Saver Fund?",
  },
  {
    Icon: ArrowLeftRight,
    question: "What is the exit load for Parag Parikh Conservative Hybrid Fund?",
  },
];

// ── Brand logos (welcome screen) ─────────────────────────────────────────────
const BrandLogos = () => (
  <div className="relative inline-flex items-center gap-3 mb-7">
    {/* Groww badge */}
    <div
      className="w-[60px] h-[60px] bg-white rounded-2xl flex items-center justify-center border border-gray-100"
      style={{ boxShadow: "0 8px 24px rgba(15,23,42,0.10)" }}
    >
      <GrowwLogoMark size={36} />
    </div>

    <span className="text-gray-300 text-xl font-light select-none">×</span>

    {/* PPFAS badge */}
    <div
      className="w-[60px] h-[60px] bg-white rounded-2xl flex items-center justify-center border border-gray-100"
      style={{ boxShadow: "0 8px 24px rgba(15,23,42,0.10)" }}
    >
      <div className="text-center leading-none px-1">
        <div className="font-black text-[10px] tracking-wider" style={{ color: "#1a3c8f" }}>
          PPFAS
        </div>
        <div className="font-semibold text-[7px] mt-0.5" style={{ color: "#e85d04" }}>
          Mutual Fund
        </div>
      </div>
    </div>

    {/* Sparkle accent */}
    <div
      className="absolute -top-2 right-0 w-6 h-6 rounded-full flex items-center justify-center"
      style={{ background: "#00d09c", boxShadow: "0 2px 8px rgba(0,208,156,0.4)" }}
    >
      <Sparkles className="w-3 h-3 text-white" />
    </div>
  </div>
);

// ── Derive a short human-readable title from the first user message ──────────
function deriveTitle(message: string): string {
  let title = message.trim().replace(/\?$/, "");
  title = title.replace(/^(what is (the )?|who is (the )?|how (much|many) (is|are) (the )?)/i, "");
  title = title.charAt(0).toUpperCase() + title.slice(1);
  return title.length > 42 ? title.slice(0, 42) + "…" : title;
}

// ────────────────────────────────────────────────────────────────────────────

export default function ChatInterface({
  activeThreadId,
  onCreateThread,
  onThreadUpdated,
  onSaveTitle,
}: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  // Always reflects the latest activeThreadId — prevents stale-closure bug
  // where an in-flight response updates the wrong thread's messages.
  const activeThreadIdRef = useRef(activeThreadId);
  // Set to true before onCreateThread() so the useEffect that fires when
  // activeThreadId changes to the new thread ID skips loadMessages() —
  // otherwise loadMessages() races with sendMessage's optimistic updates
  // and wipes them, causing the "redirects to old chat" symptom.
  const skipNextLoadRef = useRef(false);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    activeThreadIdRef.current = activeThreadId;
  }, [activeThreadId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (activeThreadId) {
      if (skipNextLoadRef.current) {
        skipNextLoadRef.current = false; // consumed — next switch loads normally
      } else {
        loadMessages();
      }
    } else {
      setMessages([]);
    }
  }, [activeThreadId]);

  const loadMessages = async () => {
    if (!activeThreadId) return;
    try {
      const response = await fetch(`${API_URL}/threads/${activeThreadId}/messages`);
      const data = await response.json();
      setMessages(data.messages || []);
    } catch (error) {
      console.error("Failed to load messages:", error);
    }
  };

  const sendMessage = async (messageText: string) => {
    if (!messageText.trim() || isLoading) return;

    let threadId = activeThreadId;
    if (!threadId) {
      // Raise the flag BEFORE the await so the useEffect that fires when
      // activeThreadId changes inside onCreateThread() sees it synchronously.
      skipNextLoadRef.current = true;
      threadId = await onCreateThread();
      if (!threadId) {
        skipNextLoadRef.current = false; // reset on failure
        return;
      }
    }

    const isFirstMessage = messages.length === 0;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: messageText }]);
    setIsLoading(true);

    try {
      const response = await fetch(`${API_URL}/threads/${threadId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: messageText }),
      });
      const data = await response.json();
      // Guard: only update messages if the user hasn't switched to a different thread
      if (activeThreadIdRef.current === threadId) {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: data.assistant_message },
        ]);
      }
      if (isFirstMessage) {
        onSaveTitle(threadId, deriveTitle(messageText));
      }
      await onThreadUpdated();
    } catch {
      if (activeThreadIdRef.current === threadId) {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: "Error: Could not reach the server." },
        ]);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await sendMessage(input);
  };

  const formatMessage = (content: string) => {
    const formatted = content.replace(
      /Source:\s*(https?:\/\/[^\s]+)/g,
      '<a href="$1" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-1 mt-2 text-xs text-[#006c4f] underline underline-offset-2 hover:text-[#005540]">Source: $1</a>'
    );
    return formatted.replace(
      /Last updated from sources:\s*(.+)/g,
      '<span class="block mt-1 text-xs text-gray-400">Last updated: $1</span>'
    );
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Facts pill */}
      <div className="flex justify-center pt-4 pb-1 flex-shrink-0">
        <div
          className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full text-xs font-medium border"
          style={{
            background: "#ffffff",
            borderColor: "#dce9ff",
            color: "#354ae4",
            boxShadow: "0 2px 8px rgba(53,74,228,0.08)",
          }}
        >
          <div className="w-1.5 h-1.5 rounded-full bg-[#354ae4]" />
          Facts-only. No investment advice.
        </div>
      </div>

      {/* Content */}
      {messages.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center px-10 text-center overflow-y-auto">
          <BrandLogos />

          <h1
            className="font-bold text-[#0b1c30] mb-3 leading-tight"
            style={{ fontSize: "26px", letterSpacing: "-0.02em" }}
          >
            Hello! I&apos;m your PPFAS
            <br />
            Mutual Fund Assistant.
          </h1>
          <p className="text-gray-400 text-sm max-w-[400px] mb-8 leading-relaxed">
            Ask me factual questions about our funds, expense ratios, exit loads, or statements.
          </p>

          {/* Question cards — full question text with icon */}
          <div className="flex flex-col gap-2 w-full max-w-[540px]">
            {QUESTIONS.map(({ Icon, question }) => (
              <button
                key={question}
                onClick={() => sendMessage(question)}
                disabled={isLoading}
                className="flex items-center gap-3 px-4 py-3 bg-white rounded-xl text-left transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                style={{
                  border: "1px solid #f0f0f0",
                  boxShadow: "0 2px 12px rgba(15,23,42,0.05)",
                }}
                onMouseEnter={(e) => {
                  if (!e.currentTarget.disabled) {
                    e.currentTarget.style.boxShadow = "0 4px 16px rgba(15,23,42,0.10)";
                    e.currentTarget.style.borderColor = "#b3e8d8";
                  }
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.boxShadow = "0 2px 12px rgba(15,23,42,0.05)";
                  e.currentTarget.style.borderColor = "#f0f0f0";
                }}
              >
                <div
                  className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                  style={{ background: "#eafaf5" }}
                >
                  <Icon className="w-4 h-4" style={{ color: "#006c4f" }} />
                </div>
                <span className="text-[14px] font-medium text-[#0b1c30]">{question}</span>
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto px-6 py-5 flex flex-col gap-4">
          {messages.map((message, index) => (
            <div
              key={index}
              className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className="max-w-[72%] px-4 py-3 rounded-2xl text-sm leading-relaxed"
                style={
                  message.role === "user"
                    ? { background: "#006c4f", color: "#ffffff", borderBottomRightRadius: "4px" }
                    : {
                        background: "#ffffff",
                        color: "#0b1c30",
                        borderBottomLeftRadius: "4px",
                        border: "1px solid #f0f0f0",
                        boxShadow: "0 2px 12px rgba(15,23,42,0.05)",
                      }
                }
              >
                <div dangerouslySetInnerHTML={{ __html: formatMessage(message.content) }} />
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="flex justify-start">
              <div
                className="px-4 py-3 rounded-2xl"
                style={{
                  background: "#ffffff",
                  border: "1px solid #f0f0f0",
                  boxShadow: "0 2px 12px rgba(15,23,42,0.05)",
                  borderBottomLeftRadius: "4px",
                }}
              >
                <div className="flex gap-1.5 items-center">
                  {[0, 150, 300].map((delay) => (
                    <div
                      key={delay}
                      className="w-2 h-2 rounded-full animate-bounce"
                      style={{ background: "#d1d5db", animationDelay: `${delay}ms` }}
                    />
                  ))}
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      )}

      {/* Input bar */}
      <div className="px-6 pb-5 pt-3 flex-shrink-0">
        <form
          onSubmit={handleSubmit}
          className="flex items-center gap-3 bg-white px-4 py-2.5 rounded-2xl"
          style={{ border: "1px solid #e8e8e8", boxShadow: "0 4px 20px rgba(15,23,42,0.07)" }}
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a factual question about PPFAS funds..."
            className="flex-1 py-1 text-sm bg-transparent outline-none"
            style={{ color: "#0b1c30" }}
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 transition-all active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed"
            style={{ background: "#006c4f" }}
            onMouseEnter={(e) => {
              if (!e.currentTarget.disabled) e.currentTarget.style.background = "#005540";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "#006c4f";
            }}
          >
            <Send className="w-4 h-4 text-white" />
          </button>
        </form>
        <p className="text-center text-[11px] text-gray-400 mt-2.5">
          Groww × PPFAS Assistant can make mistakes. Verify important financial data.
        </p>
      </div>
    </div>
  );
}

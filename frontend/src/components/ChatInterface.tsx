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

const QUESTIONS = [
  { Icon: TrendingUp,     question: "What is the NAV of Parag Parikh Flexi Cap Fund?" },
  { Icon: IndianRupee,    question: "What is the expense ratio of Parag Parikh Large Cap Fund?" },
  { Icon: BarChart2,      question: "What is the NAV of JioBlackRock Flexi Cap Fund?" },
  { Icon: ArrowLeftRight, question: "What is the minimum SIP for JioBlackRock Nifty 50 Index Fund?" },
];

const BrandLogos = () => (
  <div className="relative inline-flex items-center gap-3 mb-7">
    <div
      className="w-[60px] h-[60px] bg-white rounded-2xl flex items-center justify-center border border-gray-100"
      style={{ boxShadow: "0 8px 24px rgba(15,23,42,0.10)" }}
    >
      <img src="/groww-logo.png" alt="Groww" width={36} height={36} style={{ objectFit: "contain" }} />
    </div>

    <span className="text-gray-300 text-xl font-light select-none">×</span>

    <div
      className="w-[60px] h-[60px] bg-white rounded-2xl flex items-center justify-center border border-gray-100"
      style={{ boxShadow: "0 8px 24px rgba(15,23,42,0.10)" }}
    >
      <img src="/ppfas-logo.png" alt="PPFAS" width={40} height={40} style={{ objectFit: "contain" }} />
    </div>

    <span className="text-gray-300 text-xl font-light select-none">×</span>

    <div
      className="w-[60px] h-[60px] bg-white rounded-2xl flex items-center justify-center border border-gray-100"
      style={{ boxShadow: "0 8px 24px rgba(15,23,42,0.10)" }}
    >
      <img src="/jbr-logo.png" alt="JioBlackRock" width={58} height={58} style={{ objectFit: "contain" }} />
    </div>

    <div
      className="absolute -top-2 right-0 w-6 h-6 rounded-full flex items-center justify-center"
      style={{ background: "#00d09c", boxShadow: "0 2px 8px rgba(0,208,156,0.4)" }}
    >
      <Sparkles className="w-3 h-3 text-white" />
    </div>
  </div>
);

function deriveTitle(message: string): string {
  let title = message.trim().replace(/\?$/, "");
  title = title.replace(/^(what is (the )?|who is (the )?|how (much|many) (is|are) (the )?)/i, "");
  title = title.charAt(0).toUpperCase() + title.slice(1);
  return title.length > 42 ? title.slice(0, 42) + "…" : title;
}

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
  const activeThreadIdRef = useRef(activeThreadId);
  const skipNextLoadRef = useRef(false);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => { activeThreadIdRef.current = activeThreadId; }, [activeThreadId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (activeThreadId) {
      if (skipNextLoadRef.current) {
        skipNextLoadRef.current = false;
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

    const isFirstMessage = messages.length === 0;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: messageText }]);
    setIsLoading(true);

    let threadId = activeThreadId;
    if (!threadId) {
      try {
        skipNextLoadRef.current = true;
        threadId = await onCreateThread();
        if (!threadId) {
          skipNextLoadRef.current = false;
          throw new Error("Failed to create thread");
        }
      } catch {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: "Error: Could not reach the server. Failed to create chat session." },
        ]);
        setIsLoading(false);
        return;
      }
    }

    try {
      const response = await fetch(`${API_URL}/threads/${threadId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: messageText }),
      });
      const data = await response.json();
      if (activeThreadIdRef.current === threadId) {
        setMessages((prev) => [...prev, { role: "assistant", content: data.assistant_message }]);
      }
      if (isFirstMessage) onSaveTitle(threadId, deriveTitle(messageText));
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
    <div className="flex flex-col h-full relative">

      {/* ── Facts pill ───────────────────────────────────────── */}
      <div className="flex items-center justify-end px-6 py-3 flex-shrink-0">
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

      {/* ── Scrollable content ───────────────────────────────── */}
      <div className="flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          /* Welcome screen */
          <div className="flex flex-col items-center justify-center text-center px-6 pt-8 pb-40 min-h-full max-w-4xl mx-auto w-full">
            <BrandLogos />

            <h1
              className="font-bold text-[#0b1c30] mb-3 leading-tight"
              style={{ fontSize: "26px", letterSpacing: "-0.02em" }}
            >
              Hello! I&apos;m your Investment Assistant.
            </h1>
            <p className="text-gray-400 text-sm max-w-[460px] mb-8 leading-relaxed">
              Ask me factual questions about PPFAS and Jio BlackRock mutual funds, including expense ratios, exit loads, and statements.
            </p>

            <div className="flex flex-col gap-2 w-full max-w-[560px]">
              {QUESTIONS.map(({ Icon, question }) => (
                <button
                  key={question}
                  onClick={() => sendMessage(question)}
                  disabled={isLoading}
                  className="flex items-center gap-3 px-4 py-3 bg-white rounded-xl text-left transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  style={{ border: "1px solid #f0f0f0", boxShadow: "0 2px 12px rgba(15,23,42,0.05)" }}
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
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: "#eafaf5" }}>
                    <Icon className="w-4 h-4" style={{ color: "#006c4f" }} />
                  </div>
                  <span className="text-[14px] font-medium text-[#0b1c30]">{question}</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          /* Chat messages */
          <div className="px-6 py-5 flex flex-col gap-4 max-w-4xl mx-auto w-full pb-36">
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
      </div>

      {/* ── Fixed input bar ──────────────────────────────────── */}
      <div
        className="fixed bottom-0 left-0 md:left-64 right-0 px-6 pb-5 pt-4 pointer-events-none"
        style={{ background: "linear-gradient(to top, #f8f9ff 70%, transparent)" }}
      >
        <div className="max-w-3xl mx-auto pointer-events-auto">
          <form
            onSubmit={handleSubmit}
            className="flex items-center gap-3 bg-white px-4 py-2.5 rounded-2xl"
            style={{ border: "1px solid #e8e8e8", boxShadow: "0 4px 20px rgba(15,23,42,0.07)" }}
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a factual question about PPFAS or JioBlackRock funds…"
              className="flex-1 py-1 text-sm bg-transparent outline-none"
              style={{ color: "#0b1c30" }}
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 transition-all active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed"
              style={{ background: "#006c4f" }}
              onMouseEnter={(e) => { if (!e.currentTarget.disabled) e.currentTarget.style.background = "#005540"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "#006c4f"; }}
            >
              <Send className="w-4 h-4 text-white" />
            </button>
          </form>
          <p className="text-center text-[11px] text-gray-400 mt-2.5">
            Groww × PPFAS × JioBlackRock Assistant can make mistakes. Verify important financial data.
          </p>
        </div>
      </div>

    </div>
  );
}

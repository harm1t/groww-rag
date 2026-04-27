"use client";

import { useState, useEffect } from "react";
import { Plus, Clock, FileText, User, Settings, HelpCircle, Lock, Trash2, MessageSquare } from "lucide-react";
import ChatInterface from "@/components/ChatInterface";

interface Thread {
  id: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

// ── Groww logo mark (matches real Groww branding) ───────────────────────────
const GrowwLogoMark = ({ size = 28 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="growwBgSidebar" x1="40" y1="0" x2="0" y2="40" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#6B6FF0" />
        <stop offset="50%" stopColor="#5059D6" />
        <stop offset="100%" stopColor="#00C896" />
      </linearGradient>
      <clipPath id="growwCircleSidebar">
        <circle cx="20" cy="20" r="20" />
      </clipPath>
    </defs>
    <circle cx="20" cy="20" r="20" fill="url(#growwBgSidebar)" />
    <g clipPath="url(#growwCircleSidebar)">
      <path d="M-2 37 L5 26 L10 31 L18 19 L23 25 L31 14 L37 20 L44 13 L44 44 L-2 44 Z" fill="white" />
      <path d="M-2 32 L5 21 L10 26 L18 14 L23 20 L31 9 L37 15 L44 8 L44 38 L-2 40 Z" fill="white" opacity="0.55" />
      <path d="M-2 27 L5 16 L10 21 L18 9 L23 15 L31 4 L37 10 L44 3 L44 32 L-2 34 Z" fill="white" opacity="0.25" />
    </g>
  </svg>
);

const LOCKED_NAV = [
  { Icon: Clock, label: "Recent Analysis" },
  { Icon: FileText, label: "Tax Planning" },
  { Icon: User, label: "Account" },
];

const TITLES_KEY = "thread_titles";

function loadTitles(): Record<string, string> {
  if (typeof window === "undefined") return {};
  try { return JSON.parse(localStorage.getItem(TITLES_KEY) || "{}"); }
  catch { return {}; }
}

export default function Home() {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [threadTitles, setThreadTitles] = useState<Record<string, string>>({});

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    loadThreads();
    setThreadTitles(loadTitles());
  }, []);

  const loadThreads = async () => {
    try {
      const response = await fetch(`${API_URL}/threads`);
      const data = await response.json();
      setThreads(data.threads || []);
    } catch (error) {
      console.error("Failed to load threads:", error);
    }
  };

  const createThread = async (): Promise<string | null> => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_URL}/threads`, { method: "POST" });
      const thread = await response.json();
      setActiveThreadId(thread.id);
      await loadThreads();
      return thread.id;
    } catch (error) {
      console.error("Failed to create thread:", error);
      return null;
    } finally {
      setIsLoading(false);
    }
  };

  const saveThreadTitle = (threadId: string, title: string) => {
    setThreadTitles((prev) => {
      if (prev[threadId]) return prev;
      const next = { ...prev, [threadId]: title };
      localStorage.setItem(TITLES_KEY, JSON.stringify(next));
      return next;
    });
  };

  return (
    <main className="flex h-screen bg-[#f8f9ff] overflow-hidden">
      {/* ── Sidebar ──────────────────────────────────────────── */}
      <aside
        className="w-[260px] bg-white flex flex-col flex-shrink-0 border-r border-gray-100"
        style={{ boxShadow: "2px 0 16px rgba(15,23,42,0.04)" }}
      >
        {/* Logo */}
        <div className="px-5 py-5 border-b border-gray-50">
          <div className="flex items-center gap-2.5">
            <GrowwLogoMark size={30} />
            <div>
              <div
                className="font-bold text-[15px] leading-none tracking-tight"
                style={{ color: "#3c3c3c" }}
              >
                Groww
              </div>
              <div className="text-[11px] text-gray-400 mt-0.5">Facts-only. No advice.</div>
            </div>
          </div>
        </div>

        {/* New Chat */}
        <div className="px-4 pt-4 pb-2">
          <button
            onClick={createThread}
            disabled={isLoading}
            className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl font-semibold text-sm transition-all disabled:opacity-50"
            style={{ background: "#eafaf5", color: "#00533c" }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "#d5f5eb")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "#eafaf5")}
          >
            <div className="w-6 h-6 bg-[#00d09c] rounded-lg flex items-center justify-center flex-shrink-0">
              <Plus className="w-3.5 h-3.5 text-white" />
            </div>
            New Chat
          </button>
        </div>

        {/* Thread list */}
        <div className="flex-1 overflow-y-auto px-4 py-1">
          {threads.length > 0 && (
            <>
              <div className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider px-2 mb-1.5 mt-1">
                Recent
              </div>
              {threads.map((thread) => (
                <div
                  key={thread.id}
                  onClick={() => setActiveThreadId(thread.id)}
                  className="flex items-start gap-2.5 px-3 py-2.5 rounded-xl cursor-pointer transition-all mb-0.5"
                  style={{
                    background: activeThreadId === thread.id ? "#eafaf5" : "transparent",
                    color: activeThreadId === thread.id ? "#00533c" : "#6b7b72",
                  }}
                  onMouseEnter={(e) => {
                    if (activeThreadId !== thread.id)
                      e.currentTarget.style.background = "#f5f5f5";
                  }}
                  onMouseLeave={(e) => {
                    if (activeThreadId !== thread.id)
                      e.currentTarget.style.background = "transparent";
                  }}
                >
                  <MessageSquare className="w-3.5 h-3.5 flex-shrink-0 mt-0.5 opacity-60" />
                  <div className="min-w-0">
                    <div className="text-[13px] font-medium leading-snug line-clamp-2">
                      {threadTitles[thread.id] || `Chat ${thread.id.slice(0, 8)}`}
                    </div>
                    <div className="text-[11px] opacity-60 mt-0.5">{thread.message_count} msg</div>
                  </div>
                </div>
              ))}
            </>
          )}

          {/* Locked tools */}
          <div className="mt-3">
            <div className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider px-2 mb-1.5">
              Tools
            </div>
            {LOCKED_NAV.map(({ Icon, label }) => (
              <div
                key={label}
                className="flex items-center gap-2.5 px-3 py-2.5 rounded-xl mb-0.5 opacity-45 cursor-not-allowed select-none"
              >
                <Icon className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1">
                    <span className="text-[13px] font-medium text-gray-500 truncate">{label}</span>
                    <Lock className="w-2.5 h-2.5 text-gray-400 flex-shrink-0" />
                  </div>
                  <div className="text-[10px] text-gray-400">In development · unlocks soon</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Bottom controls */}
        <div className="px-4 pb-4 pt-3 border-t border-gray-50">
          <button
            onClick={() => { setThreads([]); setActiveThreadId(null); }}
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-[#ba1a1a] text-sm font-medium transition-all mb-1 hover:bg-red-50"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Clear History
          </button>
          <div className="flex items-center gap-2.5 px-3 py-2 rounded-xl text-gray-500 hover:bg-gray-50 transition-all cursor-pointer mb-0.5">
            <Settings className="w-3.5 h-3.5" />
            <span className="text-sm">Settings</span>
          </div>
          <div className="flex items-center gap-2.5 px-3 py-2 rounded-xl opacity-45 cursor-not-allowed select-none">
            <HelpCircle className="w-3.5 h-3.5 text-gray-400" />
            <div className="flex items-center gap-1">
              <span className="text-sm text-gray-500">Support</span>
              <Lock className="w-2.5 h-2.5 text-gray-400" />
            </div>
          </div>
        </div>
      </aside>

      {/* ── Main ─────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <ChatInterface
          activeThreadId={activeThreadId}
          onCreateThread={createThread}
          onThreadUpdated={loadThreads}
          onSaveTitle={saveThreadTitle}
        />
      </div>
    </main>
  );
}

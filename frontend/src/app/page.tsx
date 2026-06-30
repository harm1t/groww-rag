"use client";

import { useState, useEffect } from "react";
import { Plus, Trash2, MessageSquare } from "lucide-react";
import ChatInterface from "@/components/ChatInterface";
import Ticker from "@/components/Ticker";

interface Thread {
  id: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

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
    <>
      {/* ── Fixed NAV Ticker ─────────────────────────────────── */}
      <Ticker />

      {/* ── Fixed Sidebar ────────────────────────────────────── */}
      <nav
        className="hidden md:flex flex-col fixed left-0 top-9 bottom-0 w-64 bg-white border-r border-gray-100 z-50"
        style={{ boxShadow: "2px 0 16px rgba(15,23,42,0.04)" }}
      >
        {/* Logo */}
        <div className="px-5 py-5 border-b border-gray-50">
          <div className="flex items-center gap-2.5">
            <img src="/groww-logo.png" alt="Groww" width={30} height={30} style={{ objectFit: "contain" }} />
            <div>
              <div className="font-bold text-[15px] leading-none tracking-tight" style={{ color: "#3c3c3c" }}>
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
        </div>

        {/* Bottom */}
        <div className="px-4 pb-4 pt-3 border-t border-gray-50">
          <button
            onClick={() => { setThreads([]); setActiveThreadId(null); }}
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-[#ba1a1a] text-sm font-medium transition-all hover:bg-red-50"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Clear History
          </button>
        </div>
      </nav>

      {/* ── Main Content (offset by ticker + sidebar) ─────────── */}
      <div className="md:ml-64 pt-9 h-screen flex flex-col">
        <ChatInterface
          activeThreadId={activeThreadId}
          onCreateThread={createThread}
          onThreadUpdated={loadThreads}
          onSaveTitle={saveThreadTitle}
        />
      </div>
    </>
  );
}

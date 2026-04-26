"use client";

import { useState, useEffect } from "react";
import { Plus } from "lucide-react";
import ChatInterface from "@/components/ChatInterface";

interface Thread {
  id: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export default function Home() {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  // Load threads on mount
  useEffect(() => {
    loadThreads();
  }, []);

  const loadThreads = async () => {
    try {
      const response = await fetch(`${API_URL}/threads`);
      const data = await response.json();
      setThreads(data.threads || []);
    } catch (error) {
      console.error('Failed to load threads:', error);
    }
  };

  const createThread = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_URL}/threads`, {
        method: 'POST',
      });
      const thread = await response.json();
      setActiveThreadId(thread.id);
      await loadThreads();
    } catch (error) {
      console.error('Failed to create thread:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const selectThread = (threadId: string) => {
    setActiveThreadId(threadId);
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString('en-IN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <main className="flex h-screen bg-background">
      {/* Sidebar */}
      <aside className="w-[280px] bg-inverse-surface text-inverse-on-surface flex flex-col flex-shrink-0">
        <div className="p-5 border-b border-surface-container">
          <h1 className="text-h2 font-semibold text-white mb-1">PPFAS MF FAQ</h1>
          <p className="text-body-sm text-surface-dim">Facts-only assistant</p>
        </div>
        
        <button 
          onClick={createThread}
          disabled={isLoading}
          className="m-4 mt-4 bg-primary text-white rounded-lg px-4 py-2.5 font-medium transition-all hover:opacity-90 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          New Chat
        </button>
        
        <div className="flex-1 overflow-y-auto p-2">
          {threads.length === 0 ? (
            <div className="text-body-sm text-surface-dim text-center py-8">
              No recent chats
            </div>
          ) : (
            threads.map((thread) => (
              <div
                key={thread.id}
                onClick={() => selectThread(thread.id)}
                className={`p-3 rounded-lg cursor-pointer transition-all mb-1 ${
                  activeThreadId === thread.id
                    ? 'bg-surface-container text-white'
                    : 'text-surface-dim hover:bg-surface-container'
                }`}
              >
                <div className="text-body-sm font-medium">
                  Chat {thread.id.slice(0, 8)}
                </div>
                <div className="text-label-sm mt-1">
                  {formatDate(thread.updated_at)} · {thread.message_count} msgs
                </div>
              </div>
            ))
          )}
        </div>
      </aside>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="px-6 py-4 bg-surface-container-lowest border-b border-surface-container flex items-center justify-between">
          <h2 className="text-h3 font-semibold text-on-surface">
            {activeThreadId ? `Chat ${activeThreadId.slice(0, 8)}` : 'Mutual Fund FAQ Assistant'}
          </h2>
          <span className="text-label-sm text-error bg-error-container px-3 py-1 rounded-md font-medium">
            Facts-only. No investment advice.
          </span>
        </header>

        {/* Chat Interface */}
        <ChatInterface 
          activeThreadId={activeThreadId}
          onCreateThread={createThread}
          onThreadUpdated={loadThreads}
        />
      </div>
    </main>
  );
}

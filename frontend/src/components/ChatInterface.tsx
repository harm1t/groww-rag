"use client";

import { useState, useRef, useEffect } from "react";
import { Send } from "lucide-react";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface ChatInterfaceProps {
  activeThreadId: string | null;
  onCreateThread: () => Promise<void>;
  onThreadUpdated: () => Promise<void>;
}

export default function ChatInterface({ activeThreadId, onCreateThread, onThreadUpdated }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Load messages when thread changes
  useEffect(() => {
    if (activeThreadId) {
      loadMessages();
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
      console.error('Failed to load messages:', error);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    // Create thread if none exists
    if (!activeThreadId) {
      await onCreateThread();
      return;
    }

    const userMessage = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setIsLoading(true);

    try {
      const response = await fetch(`${API_URL}/threads/${activeThreadId}/messages`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ content: userMessage }),
      });

      const data = await response.json();
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.assistant_message },
      ]);
      await onThreadUpdated();
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Error: Could not reach the server." },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const askExample = async (question: string) => {
    setInput(question);
    // Create thread if none exists
    if (!activeThreadId) {
      await onCreateThread();
    }
  };

  const formatMessage = (content: string) => {
    // Format source links
    const formatted = content.replace(
      /Source:\s*(https?:\/\/[^\s]+)/g,
      '<span class="block mt-2 text-sm text-primary"><a href="$1" target="_blank" rel="noopener noreferrer" class="underline">Source: $1</a></span>'
    );
    // Format last updated lines
    return formatted.replace(
      /Last updated from sources:\s*(.+)/g,
      '<span class="block mt-1 text-xs text-on-surface-variant">Last updated from sources: $1</span>'
    );
  };

  return (
    <div className="flex-1 flex flex-col">
      {/* Messages Area */}
      {messages.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center p-10 text-center">
          <h2 className="text-h2 font-semibold text-on-surface mb-2">
            PPFAS Mutual Fund FAQ Assistant
          </h2>
          <p className="text-body-md text-on-surface-variant max-w-[500px] mb-6">
            Ask factual questions about PPFAS mutual fund schemes. This assistant provides facts only — no investment advice or comparisons.
          </p>
          <div className="flex flex-col gap-2 w-full max-w-[500px]">
            {[
              "What is the NAV of Parag Parikh Flexi Cap Fund?",
              "What is the expense ratio of Parag Parikh Large Cap Fund?",
              "What is the minimum SIP for Parag Parikh ELSS Tax Saver Fund?",
              "What is the exit load for Parag Parikh Conservative Hybrid Fund?",
            ].map((question, index) => (
              <button
                key={index}
                onClick={() => askExample(question)}
                className="text-left text-body-md px-4 py-3 rounded-lg border border-surface-container bg-surface-container-lowest hover:border-primary hover:bg-primary-container hover:text-on-primary-container transition-all"
              >
                {question}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-4">
          {messages.map((message, index) => (
            <div
              key={index}
              className={`max-w-[75%] px-4 py-3 rounded-lg ${
                message.role === "user"
                  ? "bg-primary text-on-primary rounded-br-sm self-end"
                  : "bg-surface-container-low text-on-surface rounded-bl-sm border border-surface-container self-start"
              }`}
            >
              <div
                className="text-body-md"
                dangerouslySetInnerHTML={{ __html: formatMessage(message.content) }}
              />
            </div>
          ))}
          {isLoading && (
            <div className="self-start bg-surface-container-low text-on-surface rounded-lg rounded-bl-sm px-4 py-3 border border-surface-container">
              <div className="flex gap-1">
                <div className="w-2 h-2 bg-on-surface-variant rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                <div className="w-2 h-2 bg-on-surface-variant rounded-full animate-bounce" style={{ animationDelay: "200ms" }} />
                <div className="w-2 h-2 bg-on-surface-variant rounded-full animate-bounce" style={{ animationDelay: "400ms" }} />
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      )}

      {/* Input Area */}
      <div className="p-6 bg-surface-container-lowest border-t border-surface-container">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a factual question about PPFAS funds..."
            className="flex-1 px-4 py-3 rounded-lg border border-outline bg-surface-container-low text-on-surface outline-none transition-all focus:border-primary focus:ring-2 focus:ring-primary/20 placeholder:text-on-surface-variant"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="bg-primary text-white rounded-lg px-6 py-3 font-medium transition-all hover:opacity-90 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            <Send className="w-4 h-4" />
            Send
          </button>
        </form>
      </div>
    </div>
  );
}

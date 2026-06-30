"use client";

import { useEffect, useState } from "react";

interface TickerItem {
  label: string;
  metric: string;
  value: string;
  change: string | null;
}

const METRIC_COLORS: Record<string, string> = {
  AUM:             "#2563eb",  // blue
  "Expense Ratio": "#d97706",  // amber
  "Min SIP":       "#6b7b72",  // neutral gray
};

export default function Ticker() {
  const [items, setItems] = useState<TickerItem[]>([]);
  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    fetch(`${API_URL}/ticker`)
      .then((r) => r.json())
      .then((d) => setItems(d.items || []))
      .catch(() => {});
  }, []);

  const doubled = items.length > 0 ? [...items, ...items] : [];

  function valueColor(item: TickerItem): string {
    if (item.metric === "NAV") {
      if (item.change === null)  return "#006c4f";              // brand green — no 1D data
      return item.change.startsWith("+") ? "#00a86b" : "#e53935"; // directional
    }
    return METRIC_COLORS[item.metric] ?? "#0b1c30";
  }

  return (
    <div className="fixed top-0 left-0 right-0 z-[60] h-9 bg-white border-b border-gray-200 overflow-hidden flex items-center">
      {doubled.length === 0 ? (
        <span className="px-4 text-xs text-gray-400">Loading market data…</span>
      ) : (
        <div
          className="flex items-center whitespace-nowrap animate-[marquee_350s_linear_infinite] hover:[animation-play-state:paused]"
          style={{ width: "max-content" }}
        >
          {doubled.map((item, i) => (
            <span key={i} className="inline-flex items-center text-xs px-5">
              {/* Label */}
              <span className="text-gray-500 font-medium mr-1">
                {item.label} {item.metric}:
              </span>

              {/* Value — always colored */}
              <span className="font-semibold" style={{ color: valueColor(item) }}>
                {item.value}
                {item.change && (
                  <span className="font-medium ml-0.5">
                    &nbsp;({item.change}%)
                  </span>
                )}
              </span>

              {/* Separator */}
              <span className="text-gray-300 ml-5 select-none">|</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

"use client";
import { useEffect, useState } from "react";
import { calls } from "@/lib/api";
import type { CallSession } from "@/lib/api";
import Link from "next/link";

function EmotionBar({ score }: { score?: number }) {
  if (!score) return null;
  const pct = ((score - 1) / 4) * 100;
  const color = score >= 4 ? "bg-green-400" : score >= 3 ? "bg-yellow-400" : "bg-red-400";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-500 w-6">{score.toFixed(1)}</span>
    </div>
  );
}

export default function CallsPage() {
  const [data, setData] = useState<CallSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);

  useEffect(() => {
    setLoading(true);
    calls.list(page).then(setData).finally(() => setLoading(false));
  }, [page]);

  return (
    <div className="p-8 max-w-4xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">通话记录</h1>
        <p className="text-gray-500 mt-1 text-sm">查看每次通话详情、录音和AI分析</p>
      </div>

      {loading ? (
        <div className="text-center py-12 text-gray-400">Loading...</div>
      ) : data.length === 0 ? (
        <div className="text-center py-16">
          <div className="text-5xl mb-3">📞</div>
          <div className="text-gray-500">No calls yet</div>
          <div className="text-gray-400 text-sm mt-1">Call records will appear here once your loved one starts making calls</div>
        </div>
      ) : (
        <div className="space-y-3">
          {data.map((call) => (
            <Link
              key={call.id}
              href={`/calls/${call.id}`}
              className="block bg-white rounded-2xl p-5 shadow-sm border border-gray-100 hover:border-orange-200 hover:shadow-md transition-all"
            >
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-full bg-orange-50 flex items-center justify-center text-2xl flex-shrink-0">
                  {call.alert_triggered ? "⚠️" : "📞"}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium text-gray-900">
                      {new Date(call.started_at).toLocaleDateString(undefined, {
                        year: "numeric", month: "long", day: "numeric",
                        hour: "2-digit", minute: "2-digit",
                      })}
                    </span>
                    <div className="flex items-center gap-2 text-sm text-gray-400">
                      <span>⏱ {call.duration_minutes} min</span>
                      {call.recording_url && <span>🎵 Recording available</span>}
                    </div>
                  </div>

                  <EmotionBar score={call.emotion_score} />

                  {call.ai_summary && (
                    <p className="text-sm text-gray-500 mt-2 line-clamp-2">{call.ai_summary}</p>
                  )}

                  {call.health_keywords && call.health_keywords.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {call.health_keywords.slice(0, 4).map((kw) => (
                        <span
                          key={kw}
                          className="text-xs bg-orange-50 text-orange-600 px-2 py-0.5 rounded-full"
                        >
                          {kw}
                        </span>
                      ))}
                    </div>
                  )}

                  {call.action_items && call.action_items.length > 0 && (
                    <div className="mt-2 text-xs text-blue-600 bg-blue-50 rounded-lg px-3 py-1.5">
                      📌 Follow up: {call.action_items[0]}
                    </div>
                  )}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

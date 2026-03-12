"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { calls } from "@/lib/api";
import type { CallSession, ConversationTurn } from "@/lib/api";
import Link from "next/link";

export default function CallDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [session, setSession] = useState<CallSession | null>(null);
  const [transcript, setTranscript] = useState<ConversationTurn[]>([]);
  const [loading, setLoading] = useState(true);
  const [showTranscript, setShowTranscript] = useState(false);

  useEffect(() => {
    Promise.all([
      calls.get(Number(id)).then(setSession),
      calls.getTranscript(Number(id)).then(setTranscript),
    ]).finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="p-8 text-gray-400">加载中...</div>;
  if (!session) return <div className="p-8 text-gray-400">通话记录不存在</div>;

  return (
    <div className="p-8 max-w-3xl">
      <div className="mb-6">
        <Link href="/calls" className="text-sm text-orange-500 hover:text-orange-600">
          ← 返回通话记录
        </Link>
      </div>

      {/* Alert banner */}
      {session.alert_triggered && (
        <div className="bg-red-50 border border-red-200 rounded-2xl p-4 mb-6 flex items-start gap-3">
          <span className="text-2xl">⚠️</span>
          <div>
            <div className="font-semibold text-red-700">本次通话触发了紧急提醒</div>
            <div className="text-sm text-red-600 mt-0.5">请关注老人的状况</div>
          </div>
        </div>
      )}

      {/* Summary card */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 mb-4">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h1 className="text-lg font-bold text-gray-900">
              {new Date(session.started_at).toLocaleDateString("zh-CN", {
                year: "numeric", month: "long", day: "numeric",
                hour: "2-digit", minute: "2-digit",
              })}
            </h1>
            <div className="flex items-center gap-4 mt-1 text-sm text-gray-400">
              <span>⏱ {session.duration_minutes} 分钟</span>
              {session.emotion_score && (
                <span>💛 情绪 {session.emotion_score.toFixed(1)} 分</span>
              )}
              {session.recording_url && <span>🎵 有录音</span>}
            </div>
          </div>
        </div>

        {/* AI Summary */}
        {session.ai_summary && (
          <div className="bg-orange-50 rounded-xl p-4">
            <div className="text-xs font-semibold text-orange-600 mb-2">AI 通话摘要</div>
            <p className="text-sm text-gray-700 leading-relaxed">{session.ai_summary}</p>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        {/* Health keywords */}
        {session.health_keywords && session.health_keywords.length > 0 && (
          <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100">
            <div className="text-sm font-semibold text-gray-700 mb-3">💊 健康关键词</div>
            <div className="flex flex-wrap gap-2">
              {session.health_keywords.map((kw) => (
                <span
                  key={kw}
                  className="text-sm bg-orange-50 text-orange-700 px-3 py-1 rounded-full"
                >
                  {kw}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Topics */}
        {session.topics_discussed && session.topics_discussed.length > 0 && (
          <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100">
            <div className="text-sm font-semibold text-gray-700 mb-3">💬 聊天话题</div>
            <ul className="space-y-1">
              {session.topics_discussed.map((topic) => (
                <li key={topic} className="text-sm text-gray-600 flex items-center gap-2">
                  <span className="w-1.5 h-1.5 bg-orange-400 rounded-full" />
                  {topic}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Action items */}
      {session.action_items && session.action_items.length > 0 && (
        <div className="bg-blue-50 rounded-2xl p-5 mb-4 border border-blue-100">
          <div className="text-sm font-semibold text-blue-700 mb-3">📌 家人待跟进</div>
          <ul className="space-y-2">
            {session.action_items.map((item) => (
              <li key={item} className="text-sm text-blue-700 flex items-start gap-2">
                <span className="mt-0.5">•</span>
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Recording */}
      {session.recording_url && (
        <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100 mb-4">
          <div className="text-sm font-semibold text-gray-700 mb-3">🎙 通话录音</div>
          <audio controls className="w-full" src={session.recording_url} />
        </div>
      )}

      {/* Transcript toggle */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
        <button
          onClick={() => setShowTranscript(!showTranscript)}
          className="w-full px-6 py-4 text-left flex items-center justify-between hover:bg-gray-50 transition-colors"
        >
          <span className="font-medium text-gray-900">完整对话记录 ({transcript.length} 条)</span>
          <span className="text-gray-400">{showTranscript ? "▲" : "▼"}</span>
        </button>

        {showTranscript && (
          <div className="px-6 pb-6 space-y-3 border-t border-gray-100 pt-4">
            {transcript.map((turn) => (
              <div
                key={turn.turn_number}
                className={`flex ${turn.role === "assistant" ? "justify-start" : "justify-end"}`}
              >
                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm ${
                    turn.role === "assistant"
                      ? "bg-orange-50 text-gray-700"
                      : "bg-blue-500 text-white"
                  }`}
                >
                  {turn.content}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

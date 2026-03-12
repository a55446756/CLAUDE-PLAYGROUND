"use client";
import { useEffect, useState } from "react";
import { calls, tokens, family } from "@/lib/api";
import type { CallStats, TokenBalance, ElderlyProfile, CallSession } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { formatDistanceToNow } from "date-fns";
import { zhCN } from "date-fns/locale";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";

function EmotionBadge({ score }: { score?: number }) {
  if (!score) return <span className="text-gray-400 text-sm">未分析</span>;
  if (score >= 4.5) return <span className="text-green-600 font-medium text-sm">😄 非常开心</span>;
  if (score >= 3.5) return <span className="text-green-500 font-medium text-sm">😊 心情不错</span>;
  if (score >= 2.5) return <span className="text-yellow-500 font-medium text-sm">😐 状态一般</span>;
  if (score >= 1.5) return <span className="text-orange-500 font-medium text-sm">😔 有点低落</span>;
  return <span className="text-red-500 font-medium text-sm">😢 情绪低落</span>;
}

export default function DashboardPage() {
  const { user } = useAuthStore();
  const [stats, setStats] = useState<CallStats | null>(null);
  const [balance, setBalance] = useState<TokenBalance | null>(null);
  const [elderly, setElderly] = useState<ElderlyProfile | null>(null);
  const [recentCalls, setRecentCalls] = useState<CallSession[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      calls.getStats().then(setStats),
      tokens.getBalance().then(setBalance),
      family.getElderly().then(setElderly),
      calls.list(1).then((data) => setRecentCalls(data.slice(0, 5))),
    ]).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-screen">
        <div className="text-gray-400">加载中...</div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-6xl">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">
          你好，{user?.name} 👋
        </h1>
        <p className="text-gray-500 mt-1">
          {elderly ? `正在为 ${elderly.name} 提供陪伴服务` : "欢迎使用亲声伴"}
        </p>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
          <div className="text-3xl mb-2">📞</div>
          <div className="text-2xl font-bold text-gray-900">{stats?.total_calls || 0}</div>
          <div className="text-sm text-gray-500">累计通话次数</div>
        </div>

        <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
          <div className="text-3xl mb-2">⏱️</div>
          <div className="text-2xl font-bold text-gray-900">{stats?.total_hours || 0}h</div>
          <div className="text-sm text-gray-500">累计通话时长</div>
        </div>

        <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
          <div className="text-3xl mb-2">💛</div>
          <div className="text-2xl font-bold text-gray-900">
            {stats?.avg_emotion_score?.toFixed(1) || "—"}
          </div>
          <div className="text-sm text-gray-500">平均情绪评分</div>
        </div>

        <div className={`rounded-2xl p-6 shadow-sm border ${
          (balance?.balance_minutes || 0) < 10
            ? "bg-red-50 border-red-100"
            : "bg-white border-gray-100"
        }`}>
          <div className="text-3xl mb-2">💎</div>
          <div className="text-2xl font-bold text-gray-900">
            {Math.floor(balance?.balance_minutes || 0)}分钟
          </div>
          <div className="text-sm text-gray-500">剩余通话时长</div>
          {(balance?.balance_minutes || 0) < 10 && (
            <div className="text-xs text-red-500 mt-1 font-medium">余量不足，请充值</div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Emotion trend chart */}
        <div className="lg:col-span-2 bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
          <h2 className="font-semibold text-gray-900 mb-4">近30天情绪趋势</h2>
          {stats?.emotion_trend && stats.emotion_trend.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={stats.emotion_trend}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11, fill: "#9ca3af" }}
                  tickFormatter={(v) => v.slice(5)}
                />
                <YAxis domain={[1, 5]} tick={{ fontSize: 11, fill: "#9ca3af" }} />
                <Tooltip
                  formatter={(value: number) => [`${value} 分`, "情绪评分"]}
                  labelFormatter={(label) => `日期：${label}`}
                />
                <Line
                  type="monotone"
                  dataKey="score"
                  stroke="#f97316"
                  strokeWidth={2}
                  dot={{ fill: "#f97316", r: 4 }}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-48 flex items-center justify-center text-gray-400">
              暂无通话记录
            </div>
          )}
        </div>

        {/* Elderly info */}
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
          <h2 className="font-semibold text-gray-900 mb-4">老人信息</h2>
          {elderly ? (
            <div className="space-y-3">
              <div className="flex items-center gap-3 p-3 bg-orange-50 rounded-xl">
                <span className="text-3xl">👴</span>
                <div>
                  <div className="font-semibold text-gray-900">{elderly.name}</div>
                  <div className="text-sm text-gray-500">{elderly.phone}</div>
                </div>
              </div>
              <div className="text-sm">
                <span className="text-gray-500">AI称呼：</span>
                <span className="text-gray-700">"{elderly.ai_name}"</span>
              </div>
              <div className="text-sm">
                <span className="text-gray-500">老人叫AI：</span>
                <span className="text-gray-700">"{elderly.elder_calls_ai}"</span>
              </div>
              <a
                href="/settings"
                className="block mt-2 text-center text-sm text-orange-500 hover:text-orange-600"
              >
                编辑设置 →
              </a>
            </div>
          ) : (
            <div className="text-gray-400 text-sm">未配置老人信息</div>
          )}
        </div>
      </div>

      {/* Recent calls */}
      <div className="mt-6 bg-white rounded-2xl shadow-sm border border-gray-100">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="font-semibold text-gray-900">最近通话</h2>
          <a href="/calls" className="text-sm text-orange-500 hover:text-orange-600">查看全部 →</a>
        </div>
        <div className="divide-y divide-gray-50">
          {recentCalls.length === 0 ? (
            <div className="px-6 py-8 text-center text-gray-400">暂无通话记录</div>
          ) : (
            recentCalls.map((call) => (
              <a
                key={call.id}
                href={`/calls/${call.id}`}
                className="block px-6 py-4 hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-1">
                      <span className="text-sm font-medium text-gray-900">
                        {new Date(call.started_at).toLocaleDateString("zh-CN", {
                          month: "short", day: "numeric", hour: "2-digit", minute: "2-digit"
                        })}
                      </span>
                      <span className="text-xs text-gray-400">{call.duration_minutes}分钟</span>
                      {call.alert_triggered && (
                        <span className="text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded-full font-medium">
                          ⚠ 提醒
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-500 truncate">
                      {call.ai_summary || "通话已结束"}
                    </p>
                  </div>
                  <EmotionBadge score={call.emotion_score} />
                </div>
              </a>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

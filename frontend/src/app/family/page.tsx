"use client";
import { useEffect, useState } from "react";
import { family } from "@/lib/api";
import type { FamilyUpdate } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { formatDistanceToNow } from "date-fns";
import { zhCN } from "date-fns/locale";

const CATEGORIES = [
  { value: "general", label: "日常生活", emoji: "🏡" },
  { value: "work", label: "工作事业", emoji: "💼" },
  { value: "health", label: "健康状况", emoji: "💊" },
  { value: "travel", label: "出行旅行", emoji: "✈️" },
  { value: "family", label: "家庭喜事", emoji: "🎉" },
];

export default function FamilyPage() {
  const { user } = useAuthStore();
  const [updates, setUpdates] = useState<FamilyUpdate[]>([]);
  const [showAll, setShowAll] = useState(false);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ content: "", category: "general", share_with_elderly: true });
  const [error, setError] = useState("");

  async function loadUpdates() {
    const data = await family.getUpdates(showAll);
    setUpdates(data);
  }

  useEffect(() => {
    setLoading(true);
    loadUpdates().finally(() => setLoading(false));
  }, [showAll]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.content.trim()) return;
    setError("");
    setSubmitting(true);
    try {
      await family.createUpdate(form);
      setForm({ content: "", category: "general", share_with_elderly: true });
      setShowForm(false);
      loadUpdates();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("确认删除这条动态？")) return;
    await family.deleteUpdate(id);
    loadUpdates();
  }

  const categoryMap = Object.fromEntries(CATEGORIES.map((c) => [c.value, c]));

  return (
    <div className="p-8 max-w-3xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">家庭动态</h1>
          <p className="text-gray-500 mt-1 text-sm">
            录入您的近期生活动态，AI会在通话时自然地告诉老人
          </p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-5 py-2.5 bg-orange-500 hover:bg-orange-600 text-white font-medium rounded-xl text-sm transition-colors"
        >
          + 添加动态
        </button>
      </div>

      {/* Add form */}
      {showForm && (
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 mb-6">
          <h3 className="font-semibold text-gray-900 mb-4">分享一条近况</h3>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">分类</label>
              <div className="flex flex-wrap gap-2">
                {CATEGORIES.map((cat) => (
                  <button
                    key={cat.value}
                    type="button"
                    onClick={() => setForm((f) => ({ ...f, category: cat.value }))}
                    className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                      form.category === cat.value
                        ? "bg-orange-500 text-white"
                        : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                    }`}
                  >
                    {cat.emoji} {cat.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">动态内容</label>
              <textarea
                value={form.content}
                onChange={(e) => setForm((f) => ({ ...f, content: e.target.value }))}
                placeholder="例如：我最近升职了，当了项目经理，虽然忙但很开心；周末带孩子去了动物园..."
                rows={4}
                required
                className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400 resize-none text-sm"
              />
              <p className="text-xs text-gray-400 mt-1">
                AI会把这段内容自然地融入对话，不会生硬地朗读出来
              </p>
            </div>

            <div className="flex items-center gap-3">
              <input
                type="checkbox"
                id="share"
                checked={form.share_with_elderly}
                onChange={(e) => setForm((f) => ({ ...f, share_with_elderly: e.target.checked }))}
                className="w-4 h-4 text-orange-500 rounded"
              />
              <label htmlFor="share" className="text-sm text-gray-600">
                让AI告诉老人（关闭则仅作为对话背景知识）
              </label>
            </div>

            {error && (
              <div className="bg-red-50 text-red-600 text-sm rounded-lg px-4 py-3">{error}</div>
            )}

            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="flex-1 py-2.5 border border-gray-200 text-gray-600 rounded-xl text-sm hover:bg-gray-50"
              >
                取消
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="flex-1 py-2.5 bg-orange-500 hover:bg-orange-600 disabled:bg-orange-300 text-white rounded-xl text-sm font-medium"
              >
                {submitting ? "提交中..." : "发布动态"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Toggle */}
      <div className="flex gap-3 mb-4">
        <button
          onClick={() => setShowAll(false)}
          className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
            !showAll ? "bg-orange-500 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
          }`}
        >
          待播报 ({updates.filter((u) => !u.has_been_shared).length})
        </button>
        <button
          onClick={() => setShowAll(true)}
          className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
            showAll ? "bg-orange-500 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
          }`}
        >
          全部记录
        </button>
      </div>

      {/* Updates list */}
      {loading ? (
        <div className="text-center py-8 text-gray-400">加载中...</div>
      ) : updates.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <div className="text-4xl mb-3">💌</div>
          <div>{showAll ? "暂无动态记录" : "当前没有待播报的动态"}</div>
          <div className="text-sm mt-1">点击上方"添加动态"，让AI代您告诉老人您的近况</div>
        </div>
      ) : (
        <div className="space-y-3">
          {updates.map((update) => {
            const cat = categoryMap[update.category] || categoryMap.general;
            return (
              <div
                key={update.id}
                className={`bg-white rounded-2xl p-5 shadow-sm border transition-opacity ${
                  update.has_been_shared ? "border-gray-100 opacity-60" : "border-orange-100"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-base">{cat.emoji}</span>
                      <span className="text-xs font-medium text-gray-500">{cat.label}</span>
                      <span className="text-xs text-gray-400">•</span>
                      <span className="text-xs text-gray-500">
                        {update.author_name}（{update.relation_to_elderly}）
                      </span>
                      {update.has_been_shared && (
                        <span className="text-xs bg-green-100 text-green-600 px-2 py-0.5 rounded-full">
                          已播报
                        </span>
                      )}
                      {!update.share_with_elderly && (
                        <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">
                          仅上下文
                        </span>
                      )}
                    </div>
                    <p className="text-gray-700 text-sm leading-relaxed">{update.content}</p>
                    <p className="text-xs text-gray-400 mt-2">
                      {formatDistanceToNow(new Date(update.created_at), {
                        addSuffix: true,
                        locale: zhCN,
                      })}
                    </p>
                  </div>
                  {!update.has_been_shared && (
                    <button
                      onClick={() => handleDelete(update.id)}
                      className="text-gray-300 hover:text-red-400 text-lg transition-colors flex-shrink-0"
                    >
                      ×
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

"use client";
import { useEffect, useState } from "react";
import { family } from "@/lib/api";
import type { ElderlyProfile } from "@/lib/api";

export default function SettingsPage() {
  const [elderly, setElderly] = useState<ElderlyProfile | null>(null);
  const [form, setForm] = useState<Partial<ElderlyProfile>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    family.getElderly().then((data) => {
      setElderly(data);
      setForm(data);
    }).finally(() => setLoading(false));
  }, []);

  function update(field: keyof ElderlyProfile, value: string) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      const updated = await family.updateElderly(form);
      setElderly(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="p-8 text-gray-400">加载中...</div>;

  return (
    <div className="p-8 max-w-2xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">老人设置</h1>
        <p className="text-gray-500 mt-1 text-sm">配置老人的个人信息，让AI的陪伴更贴心</p>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* Basic info */}
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
          <h2 className="font-semibold text-gray-900 mb-4">基本信息</h2>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">老人名字</label>
                <input
                  value={form.name || ""}
                  onChange={(e) => update("name", e.target.value)}
                  className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">手机号</label>
                <input
                  value={form.phone || ""}
                  disabled
                  className="w-full px-4 py-3 border border-gray-200 rounded-xl bg-gray-50 text-gray-400 text-sm cursor-not-allowed"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">AI自称什么</label>
                <input
                  value={form.ai_name || ""}
                  onChange={(e) => update("ai_name", e.target.value)}
                  placeholder="例如：小明、女儿、孩子"
                  className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400 text-sm"
                />
                <p className="text-xs text-gray-400 mt-1">AI打招呼时会说"我是{form.ai_name || "孩子"}啊"</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">老人叫AI什么</label>
                <input
                  value={form.elder_calls_ai || ""}
                  onChange={(e) => update("elder_calls_ai", e.target.value)}
                  placeholder="例如：小明、大宝、孩子"
                  className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400 text-sm"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Personality */}
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
          <h2 className="font-semibold text-gray-900 mb-1">性格与特点</h2>
          <p className="text-xs text-gray-400 mb-4">帮助AI更好地了解老人，提供更贴心的陪伴</p>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">性格特点</label>
              <textarea
                value={form.personality_notes || ""}
                onChange={(e) => update("personality_notes", e.target.value)}
                placeholder="例如：性格开朗，喜欢聊家常，有时候会担心孩子太忙，爱听戏曲..."
                rows={3}
                className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400 resize-none text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">兴趣爱好</label>
              <textarea
                value={form.interests || ""}
                onChange={(e) => update("interests", e.target.value)}
                placeholder="例如：喜欢跳广场舞、看电视剧、打麻将、聊孙子的事情..."
                rows={2}
                className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400 resize-none text-sm"
              />
            </div>
          </div>
        </div>

        {/* Health */}
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
          <h2 className="font-semibold text-gray-900 mb-1">健康情况</h2>
          <p className="text-xs text-gray-400 mb-4">AI会据此调整关心方式，有健康问题会特别注意</p>
          <textarea
            value={form.health_notes || ""}
            onChange={(e) => update("health_notes", e.target.value)}
            placeholder="例如：有高血压，需要按时吃药；膝盖不好，不能爬山；有糖尿病，注意饮食..."
            rows={3}
            className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400 resize-none text-sm"
          />
        </div>

        {error && (
          <div className="bg-red-50 text-red-600 text-sm rounded-xl px-4 py-3">{error}</div>
        )}
        {saved && (
          <div className="bg-green-50 text-green-600 text-sm rounded-xl px-4 py-3">
            设置已保存 ✓
          </div>
        )}

        <button
          type="submit"
          disabled={saving}
          className="w-full py-3.5 bg-orange-500 hover:bg-orange-600 disabled:bg-orange-300 text-white font-semibold rounded-xl transition-colors"
        >
          {saving ? "保存中..." : "保存设置"}
        </button>
      </form>
    </div>
  );
}

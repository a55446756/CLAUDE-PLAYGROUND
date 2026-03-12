"use client";
import { useEffect, useState } from "react";
import { family } from "@/lib/api";
import type { ElderlyProfile } from "@/lib/api";

const LANGUAGES = [
  { value: "en-US", label: "English (US)" },
  { value: "en-GB", label: "English (UK)" },
  { value: "zh-CN", label: "中文（普通话）" },
  { value: "zh-TW", label: "中文（繁體）" },
  { value: "es-ES", label: "Español (España)" },
  { value: "es-US", label: "Español (Latinoamérica)" },
  { value: "fr-FR", label: "Français" },
  { value: "de-DE", label: "Deutsch" },
  { value: "ja-JP", label: "日本語" },
  { value: "ko-KR", label: "한국어" },
  { value: "pt-BR", label: "Português (Brasil)" },
  { value: "it-IT", label: "Italiano" },
];

const TIMEZONES = [
  "UTC", "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
  "America/Toronto", "America/Vancouver", "America/Sao_Paulo", "America/Buenos_Aires",
  "Europe/London", "Europe/Paris", "Europe/Berlin", "Europe/Madrid", "Europe/Rome",
  "Europe/Moscow", "Asia/Shanghai", "Asia/Tokyo", "Asia/Seoul", "Asia/Kolkata",
  "Asia/Dubai", "Asia/Singapore", "Australia/Sydney", "Pacific/Auckland",
];

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

  if (loading) return <div className="p-8 text-gray-400">Loading...</div>;

  return (
    <div className="p-8 max-w-2xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Profile Settings</h1>
        <p className="text-gray-500 mt-1 text-sm">
          Configure your loved one&apos;s profile to make AI conversations more personal
        </p>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* Basic info */}
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
          <h2 className="font-semibold text-gray-900 mb-4">Basic Information</h2>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Their name</label>
                <input value={form.name || ""}
                  onChange={(e) => update("name", e.target.value)}
                  className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400 text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Phone number</label>
                <input value={form.phone || ""} disabled
                  className="w-full px-4 py-3 border border-gray-200 rounded-xl bg-gray-50 text-gray-400 text-sm cursor-not-allowed" />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">AI introduces itself as</label>
                <input value={form.ai_name || ""}
                  onChange={(e) => update("ai_name", e.target.value)}
                  placeholder="e.g. Sarah, your daughter"
                  className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400 text-sm" />
                <p className="text-xs text-gray-400 mt-1">AI says &quot;Hi, it&apos;s {form.ai_name || "your name"}!&quot;</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">They call the AI</label>
                <input value={form.elder_calls_ai || ""}
                  onChange={(e) => update("elder_calls_ai", e.target.value)}
                  placeholder="e.g. Sarah, dear"
                  className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400 text-sm" />
              </div>
            </div>
          </div>
        </div>

        {/* Language & Location */}
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
          <h2 className="font-semibold text-gray-900 mb-1">Language & Location</h2>
          <p className="text-xs text-gray-400 mb-4">
            Determines the language the AI speaks and the voice used during calls
          </p>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Conversation language</label>
              <select value={form.language || "en-US"}
                onChange={(e) => update("language", e.target.value)}
                className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400 text-sm">
                {LANGUAGES.map((l) => (
                  <option key={l.value} value={l.value}>{l.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Timezone</label>
              <select value={form.timezone || "UTC"}
                onChange={(e) => update("timezone", e.target.value)}
                className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400 text-sm">
                {TIMEZONES.map((tz) => (
                  <option key={tz} value={tz}>{tz}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Personality */}
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
          <h2 className="font-semibold text-gray-900 mb-1">Personality & Interests</h2>
          <p className="text-xs text-gray-400 mb-4">
            Help the AI have more meaningful, personalized conversations
          </p>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Personality notes</label>
              <textarea value={form.personality_notes || ""}
                onChange={(e) => update("personality_notes", e.target.value)}
                placeholder="e.g. Very cheerful, loves talking about the grandchildren, worries about the family sometimes, enjoys music from the 60s..."
                rows={3}
                className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400 resize-none text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Hobbies & interests</label>
              <textarea value={form.interests || ""}
                onChange={(e) => update("interests", e.target.value)}
                placeholder="e.g. Gardening, cooking, watching tennis, knitting, stories about the old days..."
                rows={2}
                className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400 resize-none text-sm" />
            </div>
          </div>
        </div>

        {/* Health notes */}
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
          <h2 className="font-semibold text-gray-900 mb-1">Health Notes</h2>
          <p className="text-xs text-gray-400 mb-4">
            The AI will pay special attention to these and gently encourage care
          </p>
          <textarea value={form.health_notes || ""}
            onChange={(e) => update("health_notes", e.target.value)}
            placeholder="e.g. Has high blood pressure — needs to take medication. Knee problems, avoid suggesting physical activities. Mild hearing difficulty — AI should speak slowly and clearly..."
            rows={3}
            className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400 resize-none text-sm" />
        </div>

        {error && (
          <div className="bg-red-50 text-red-600 text-sm rounded-xl px-4 py-3">{error}</div>
        )}
        {saved && (
          <div className="bg-green-50 text-green-600 text-sm rounded-xl px-4 py-3">
            Settings saved successfully ✓
          </div>
        )}

        <button type="submit" disabled={saving}
          className="w-full py-3.5 bg-orange-500 hover:bg-orange-600 disabled:bg-orange-300 text-white font-semibold rounded-xl transition-colors">
          {saving ? "Saving..." : "Save settings"}
        </button>
      </form>
    </div>
  );
}

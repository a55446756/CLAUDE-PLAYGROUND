"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { auth } from "@/lib/api";
import { useAuthStore } from "@/lib/store";

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

export default function RegisterPage() {
  const router = useRouter();
  const { setAuth } = useAuthStore();
  const [step, setStep] = useState<1 | 2>(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [form, setForm] = useState({
    name: "",
    phone: "",
    password: "",
    relation_to_elderly: "son/daughter",
    family_name: "",
    elderly_name: "",
    elderly_phone: "",
    elderly_language: "en-US",
    elderly_timezone: "UTC",
    elderly_country: "US",
    ai_name: "",
  });

  function update(field: string, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (step === 1) { setStep(2); return; }

    setError("");
    setLoading(true);
    try {
      const res = await auth.register({
        name: form.name,
        phone: form.phone,
        password: form.password,
        relation_to_elderly: form.relation_to_elderly,
        family_name: form.family_name,
        elderly_name: form.elderly_name,
        elderly_phone: form.elderly_phone,
        elderly_language: form.elderly_language,
        elderly_timezone: form.elderly_timezone,
        elderly_country: form.elderly_country,
        ai_name: form.ai_name || form.name,
      });
      const me = await auth.me();
      setAuth(res.access_token, me);
      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message || "Registration failed, please try again");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-orange-50 to-amber-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="text-5xl mb-3">🫂</div>
          <h1 className="text-3xl font-bold text-gray-900">CompanionCall</h1>
          <p className="text-gray-500 mt-2">Create your family account</p>
        </div>

        <div className="bg-white rounded-2xl shadow-lg p-8">
          <div className="flex items-center gap-3 mb-6">
            <div className={`flex-1 h-1 rounded-full ${step >= 1 ? "bg-orange-500" : "bg-gray-200"}`} />
            <div className={`flex-1 h-1 rounded-full ${step >= 2 ? "bg-orange-500" : "bg-gray-200"}`} />
          </div>
          <p className="text-sm text-gray-500 mb-6">
            {step === 1 ? "Step 1: Your details" : "Step 2: Your loved one's details"}
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            {step === 1 && (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Your name</label>
                  <input value={form.name} onChange={(e) => update("name", e.target.value)}
                    placeholder="e.g. Sarah Johnson" required
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Phone number</label>
                  <input type="tel" value={form.phone} onChange={(e) => update("phone", e.target.value)}
                    placeholder="+12125551234" required
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400" />
                  <p className="text-xs text-gray-400 mt-1">International format: +1 for US/CA, +44 for UK, +86 for CN, etc.</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
                  <input type="password" value={form.password} onChange={(e) => update("password", e.target.value)}
                    placeholder="At least 6 characters" minLength={6} required
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Your relationship to them</label>
                  <input value={form.relation_to_elderly} onChange={(e) => update("relation_to_elderly", e.target.value)}
                    placeholder="e.g. daughter, son, grandson"
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400" />
                </div>
              </>
            )}

            {step === 2 && (
              <>
                <div className="bg-orange-50 rounded-xl p-4 text-sm text-orange-700">
                  Your loved one needs no app — they just dial one phone number to chat with the AI companion.
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Family / account name</label>
                  <input value={form.family_name} onChange={(e) => update("family_name", e.target.value)}
                    placeholder="e.g. The Johnson Family" required
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Their name</label>
                  <input value={form.elderly_name} onChange={(e) => update("elderly_name", e.target.value)}
                    placeholder="e.g. Grandma Rose" required
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Their phone number</label>
                  <input type="tel" value={form.elderly_phone} onChange={(e) => update("elderly_phone", e.target.value)}
                    placeholder="+12125551234" required
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Conversation language
                  </label>
                  <select value={form.elderly_language} onChange={(e) => update("elderly_language", e.target.value)}
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400">
                    {LANGUAGES.map((l) => (
                      <option key={l.value} value={l.value}>{l.label}</option>
                    ))}
                  </select>
                  <p className="text-xs text-gray-400 mt-1">The AI will speak and understand this language during calls</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Their timezone</label>
                  <select value={form.elderly_timezone} onChange={(e) => update("elderly_timezone", e.target.value)}
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400">
                    {TIMEZONES.map((tz) => (
                      <option key={tz} value={tz}>{tz}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">AI companion name</label>
                  <input value={form.ai_name} onChange={(e) => update("ai_name", e.target.value)}
                    placeholder={`The AI will introduce itself as "${form.name || "your name"}"`}
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400" />
                  <p className="text-xs text-gray-400 mt-1">Leave blank to use your name</p>
                </div>
              </>
            )}

            {error && (
              <div className="bg-red-50 text-red-600 text-sm rounded-lg px-4 py-3">{error}</div>
            )}

            <div className="flex gap-3">
              {step === 2 && (
                <button type="button" onClick={() => setStep(1)}
                  className="flex-1 py-3 border border-gray-200 text-gray-600 font-semibold rounded-xl hover:bg-gray-50 transition-colors">
                  Back
                </button>
              )}
              <button type="submit" disabled={loading}
                className="flex-1 py-3 bg-orange-500 hover:bg-orange-600 disabled:bg-orange-300 text-white font-semibold rounded-xl transition-colors">
                {loading ? "Creating account..." : step === 1 ? "Next" : "Create account"}
              </button>
            </div>
          </form>

          <p className="text-center text-sm text-gray-500 mt-6">
            Already have an account?{" "}
            <Link href="/auth/login" className="text-orange-500 hover:text-orange-600 font-medium">Sign in</Link>
          </p>
        </div>
      </div>
    </div>
  );
}

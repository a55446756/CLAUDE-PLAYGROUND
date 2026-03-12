"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { auth } from "@/lib/api";
import { useAuthStore } from "@/lib/store";

export default function RegisterPage() {
  const router = useRouter();
  const { setAuth } = useAuthStore();
  const [step, setStep] = useState<1 | 2>(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [form, setForm] = useState({
    // Member info
    name: "",
    phone: "",
    password: "",
    relation_to_elderly: "子女",
    // Family/elderly info
    family_name: "",
    elderly_name: "",
    elderly_phone: "",
    ai_name: "",
  });

  function update(field: string, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (step === 1) {
      setStep(2);
      return;
    }

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
        ai_name: form.ai_name || form.name,
      });
      const me = await auth.me();
      setAuth(res.access_token, me);
      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message || "注册失败，请重试");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-orange-50 to-amber-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="text-5xl mb-3">🫂</div>
          <h1 className="text-3xl font-bold text-gray-900">亲声伴</h1>
          <p className="text-gray-500 mt-2">注册账号，开始陪伴</p>
        </div>

        <div className="bg-white rounded-2xl shadow-lg p-8">
          {/* Step indicator */}
          <div className="flex items-center gap-3 mb-6">
            <div className={`flex-1 h-1 rounded-full ${step >= 1 ? "bg-orange-500" : "bg-gray-200"}`} />
            <div className={`flex-1 h-1 rounded-full ${step >= 2 ? "bg-orange-500" : "bg-gray-200"}`} />
          </div>
          <p className="text-sm text-gray-500 mb-6">
            {step === 1 ? "第一步：您的信息" : "第二步：老人信息"}
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            {step === 1 && (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">您的姓名</label>
                  <input
                    value={form.name}
                    onChange={(e) => update("name", e.target.value)}
                    placeholder="例如：张小明"
                    required
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">手机号</label>
                  <input
                    type="tel"
                    value={form.phone}
                    onChange={(e) => update("phone", e.target.value)}
                    placeholder="请输入您的手机号"
                    required
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">密码</label>
                  <input
                    type="password"
                    value={form.password}
                    onChange={(e) => update("password", e.target.value)}
                    placeholder="至少8位"
                    minLength={6}
                    required
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">您与老人的关系</label>
                  <select
                    value={form.relation_to_elderly}
                    onChange={(e) => update("relation_to_elderly", e.target.value)}
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400"
                  >
                    <option value="大儿子">大儿子</option>
                    <option value="二儿子">二儿子</option>
                    <option value="大女儿">大女儿</option>
                    <option value="二女儿">二女儿</option>
                    <option value="子女">子女</option>
                    <option value="孙子">孙子</option>
                    <option value="孙女">孙女</option>
                    <option value="其他亲属">其他亲属</option>
                  </select>
                </div>
              </>
            )}

            {step === 2 && (
              <>
                <div className="bg-orange-50 rounded-xl p-4 text-sm text-orange-700">
                  老人不需要下载任何 App，只需要记住一个电话号码即可
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">家庭名称</label>
                  <input
                    value={form.family_name}
                    onChange={(e) => update("family_name", e.target.value)}
                    placeholder="例如：张家"
                    required
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">老人的名字</label>
                  <input
                    value={form.elderly_name}
                    onChange={(e) => update("elderly_name", e.target.value)}
                    placeholder="例如：张奶奶"
                    required
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">老人的手机号</label>
                  <input
                    type="tel"
                    value={form.elderly_phone}
                    onChange={(e) => update("elderly_phone", e.target.value)}
                    placeholder="老人拨出电话的号码"
                    required
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">AI代表谁？</label>
                  <input
                    value={form.ai_name}
                    onChange={(e) => update("ai_name", e.target.value)}
                    placeholder={`AI以"${form.name || "孩子"}"的名义和老人说话`}
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400"
                  />
                  <p className="text-xs text-gray-400 mt-1">留空则默认用您的姓名</p>
                </div>
              </>
            )}

            {error && (
              <div className="bg-red-50 text-red-600 text-sm rounded-lg px-4 py-3">{error}</div>
            )}

            <div className="flex gap-3">
              {step === 2 && (
                <button
                  type="button"
                  onClick={() => setStep(1)}
                  className="flex-1 py-3 border border-gray-200 text-gray-600 font-semibold rounded-xl hover:bg-gray-50 transition-colors"
                >
                  上一步
                </button>
              )}
              <button
                type="submit"
                disabled={loading}
                className="flex-1 py-3 bg-orange-500 hover:bg-orange-600 disabled:bg-orange-300 text-white font-semibold rounded-xl transition-colors"
              >
                {loading ? "注册中..." : step === 1 ? "下一步" : "完成注册"}
              </button>
            </div>
          </form>

          <p className="text-center text-sm text-gray-500 mt-6">
            已有账号？{" "}
            <Link href="/auth/login" className="text-orange-500 hover:text-orange-600 font-medium">
              立即登录
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}

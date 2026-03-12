"use client";
import { useEffect, useState } from "react";
import { tokens } from "@/lib/api";
import type { TokenBalance, TokenPackage, TokenTransaction } from "@/lib/api";

const TYPE_LABELS: Record<string, string> = {
  purchase: "充值",
  free_trial: "赠送",
  refund: "退款",
  usage: "通话消耗",
  admin_grant: "管理员赠送",
};

export default function TokensPage() {
  const [balance, setBalance] = useState<TokenBalance | null>(null);
  const [packages, setPackages] = useState<TokenPackage[]>([]);
  const [transactions, setTransactions] = useState<TokenTransaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [mocking, setMocking] = useState(false);

  async function load() {
    const [bal, pkgs, txns] = await Promise.all([
      tokens.getBalance(),
      tokens.getPackages(),
      tokens.getTransactions(),
    ]);
    setBalance(bal);
    setPackages(pkgs);
    setTransactions(txns);
  }

  useEffect(() => {
    load().finally(() => setLoading(false));
  }, []);

  async function handleMockRecharge(minutes: number) {
    setMocking(true);
    try {
      await tokens.mockRecharge(minutes);
      await load();
    } finally {
      setMocking(false);
    }
  }

  if (loading) return <div className="p-8 text-gray-400">加载中...</div>;

  return (
    <div className="p-8 max-w-3xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">时长充值</h1>
        <p className="text-gray-500 mt-1 text-sm">管理通话时长余额</p>
      </div>

      {/* Balance */}
      <div className={`rounded-2xl p-6 mb-8 ${
        (balance?.balance_minutes || 0) < 30
          ? "bg-gradient-to-r from-red-50 to-orange-50 border border-red-100"
          : "bg-gradient-to-r from-orange-50 to-amber-50 border border-orange-100"
      }`}>
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm font-medium text-gray-600 mb-1">当前余额</div>
            <div className="text-4xl font-bold text-gray-900">
              {Math.floor(balance?.balance_minutes || 0)}
              <span className="text-xl font-normal text-gray-500 ml-1">分钟</span>
            </div>
            <div className="text-sm text-gray-400 mt-1">
              约 {balance?.balance_hours?.toFixed(1)} 小时
            </div>
          </div>
          <div className="text-6xl opacity-30">💎</div>
        </div>
        {(balance?.balance_minutes || 0) < 30 && (
          <div className="mt-3 text-sm text-red-600 font-medium">
            ⚠ 余额不足，建议立即充值以保证正常使用
          </div>
        )}
      </div>

      {/* Dev mock recharge */}
      <div className="bg-yellow-50 border border-yellow-200 rounded-2xl p-4 mb-8">
        <div className="text-sm font-semibold text-yellow-800 mb-2">🛠 开发测试充值</div>
        <div className="flex gap-2 flex-wrap">
          {[30, 60, 300].map((min) => (
            <button
              key={min}
              onClick={() => handleMockRecharge(min)}
              disabled={mocking}
              className="px-4 py-2 bg-yellow-500 hover:bg-yellow-600 text-white text-sm rounded-xl font-medium disabled:opacity-50"
            >
              +{min}分钟
            </button>
          ))}
        </div>
        <p className="text-xs text-yellow-600 mt-2">此功能仅供开发测试使用，正式版将接入支付系统</p>
      </div>

      {/* Packages */}
      <h2 className="font-semibold text-gray-900 mb-4">充值套餐</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        {packages.map((pkg) => (
          <div
            key={pkg.id}
            className={`bg-white rounded-2xl p-5 shadow-sm border cursor-pointer transition-all hover:shadow-md ${
              pkg.name === "月卡标准版"
                ? "border-orange-400 ring-2 ring-orange-200"
                : "border-gray-100"
            }`}
          >
            {pkg.name === "月卡标准版" && (
              <div className="text-xs bg-orange-500 text-white px-2 py-0.5 rounded-full inline-block mb-2 font-medium">
                推荐
              </div>
            )}
            <div className="font-bold text-gray-900 text-lg">{pkg.name}</div>
            <div className="text-gray-500 text-sm mt-0.5">{pkg.description}</div>
            <div className="mt-3 flex items-baseline gap-1">
              {pkg.price_cents === 0 ? (
                <span className="text-2xl font-bold text-green-500">免费</span>
              ) : (
                <>
                  <span className="text-2xl font-bold text-gray-900">
                    ¥{(pkg.price_cents / 100).toFixed(0)}
                  </span>
                  {pkg.subscription_interval && (
                    <span className="text-sm text-gray-400">/{pkg.subscription_interval === "month" ? "月" : "年"}</span>
                  )}
                </>
              )}
            </div>
            <div className="text-sm text-orange-600 font-medium mt-1">
              {pkg.minutes >= 99999 ? "不限时长" : `${pkg.minutes} 分钟`}
            </div>
            <button className="mt-4 w-full py-2.5 bg-orange-500 hover:bg-orange-600 text-white text-sm font-semibold rounded-xl transition-colors">
              {pkg.price_cents === 0 ? "已领取" : "立即购买"}
            </button>
          </div>
        ))}
      </div>

      {/* Transaction history */}
      <h2 className="font-semibold text-gray-900 mb-4">消费记录</h2>
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
        {transactions.length === 0 ? (
          <div className="py-8 text-center text-gray-400">暂无记录</div>
        ) : (
          <div className="divide-y divide-gray-50">
            {transactions.map((txn) => (
              <div key={txn.id} className="px-5 py-4 flex items-center justify-between">
                <div>
                  <div className="text-sm font-medium text-gray-900">
                    {TYPE_LABELS[txn.transaction_type] || txn.transaction_type}
                  </div>
                  <div className="text-xs text-gray-400">
                    {txn.description} • {new Date(txn.created_at).toLocaleDateString("zh-CN")}
                  </div>
                </div>
                <div className={`text-sm font-semibold ${
                  txn.seconds_delta > 0 ? "text-green-500" : "text-gray-400"
                }`}>
                  {txn.seconds_delta > 0 ? "+" : ""}{Math.round(txn.seconds_delta / 60)}分钟
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

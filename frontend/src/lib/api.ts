const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (res.status === 401) {
    localStorage.removeItem("token");
    window.location.href = "/auth/login";
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || "Request failed");
  }

  if (res.status === 204) return null as T;
  return res.json();
}

// --- Auth ---
export const auth = {
  register: (data: RegisterRequest) =>
    request<TokenResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  login: (phone: string, password: string) =>
    request<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ phone, password }),
    }),

  me: () => request<MeResponse>("/auth/me"),
};

// --- Family ---
export const family = {
  getElderly: () => request<ElderlyProfile>("/family/elderly"),

  updateElderly: (data: Partial<ElderlyProfile>) =>
    request<ElderlyProfile>("/family/elderly", {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  getMembers: () => request<FamilyMember[]>("/family/members"),

  getUpdates: (includeShared = false) =>
    request<FamilyUpdate[]>(`/family/updates?include_shared=${includeShared}`),

  createUpdate: (data: CreateUpdateRequest) =>
    request<FamilyUpdate>("/family/updates", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  deleteUpdate: (id: number) =>
    request(`/family/updates/${id}`, { method: "DELETE" }),
};

// --- Calls ---
export const calls = {
  list: (page = 1) => request<CallSession[]>(`/calls/?page=${page}`),
  get: (id: number) => request<CallSession>(`/calls/${id}`),
  getTranscript: (id: number) => request<ConversationTurn[]>(`/calls/${id}/transcript`),
  getStats: () => request<CallStats>("/calls/stats/overview"),
};

// --- Tokens ---
export const tokens = {
  getBalance: () => request<TokenBalance>("/tokens/balance"),
  getPackages: () => request<TokenPackage[]>("/tokens/packages"),
  getTransactions: () => request<TokenTransaction[]>("/tokens/transactions"),
  mockRecharge: (minutes: number) =>
    request(`/tokens/mock-recharge?minutes=${minutes}`, { method: "POST" }),
};

// --- Types ---
export interface RegisterRequest {
  name: string;
  phone: string;
  password: string;
  email?: string;
  elderly_name: string;
  elderly_phone: string;
  family_name: string;
  relation_to_elderly: string;
  ai_name: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  member_id: number;
  name: string;
  family_group_id: number;
}

export interface MeResponse {
  id: number;
  name: string;
  phone: string;
  email?: string;
  role: string;
  family_group_id: number;
  token_balance_minutes: number;
  relation_to_elderly: string;
}

export interface ElderlyProfile {
  id: number;
  name: string;
  phone: string;
  ai_name: string;
  elder_calls_ai: string;
  personality_notes: string;
  health_notes: string;
  interests: string;
}

export interface FamilyMember {
  id: number;
  name: string;
  phone: string;
  role: string;
  relation_to_elderly: string;
  token_balance_minutes: number;
  is_active: boolean;
}

export interface FamilyUpdate {
  id: number;
  author_name: string;
  relation_to_elderly: string;
  content: string;
  category: string;
  share_with_elderly: boolean;
  has_been_shared: boolean;
  created_at: string;
}

export interface CreateUpdateRequest {
  content: string;
  category: string;
  share_with_elderly: boolean;
  expires_days?: number;
}

export interface CallSession {
  id: number;
  started_at: string;
  ended_at?: string;
  duration_minutes: number;
  emotion_score?: number;
  emotion_description?: string;
  ai_summary?: string;
  health_keywords: string[];
  topics_discussed: string[];
  action_items: string[];
  alert_triggered: boolean;
  recording_url?: string;
}

export interface ConversationTurn {
  turn_number: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface CallStats {
  total_calls: number;
  total_hours: number;
  avg_emotion_score?: number;
  emotion_trend: Array<{ date: string; score: number; duration_minutes: number }>;
  recent_calls_count: number;
}

export interface TokenBalance {
  balance_seconds: number;
  balance_minutes: number;
  balance_hours: number;
}

export interface TokenPackage {
  id: number;
  name: string;
  description: string;
  minutes: number;
  price_cents: number;
  currency: string;
  is_subscription: boolean;
  subscription_interval?: string;
}

export interface TokenTransaction {
  id: number;
  transaction_type: string;
  seconds_delta: number;
  balance_after: number;
  description: string;
  created_at: string;
}

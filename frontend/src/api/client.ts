const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

/** Token provider injected at runtime via useApiClient hook. */
let _tokenProvider: (() => Promise<string>) | null = null;

/** Set the token provider (called from useApiClient hook). */
export function setTokenProvider(fn: () => Promise<string>): void {
  _tokenProvider = fn;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  authenticated?: boolean;
}

/**
 * Thin HTTP client that attaches a JWT bearer token for
 * authenticated requests.
 */
async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { method = "GET", body, authenticated = false } = options;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (authenticated && _tokenProvider) {
    const token = await _tokenProvider();
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    throw new Error(`API ${method} ${path} failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

/**
 * API client with methods for each backend endpoint.
 * Unauthenticated calls (search) do not attach a token.
 */
export const apiClient = {
  /** Anonymous search (rate-limited). */
  search: (query: string, top = 5) =>
    request<{ results: unknown[] }>("/search", {
      method: "POST",
      body: { query, top },
    }),

  /** Authenticated chat. */
  chat: (message: string, conversationId?: string) =>
    request<{ answer: string; citations: unknown[]; conversation_id: string }>(
      "/chat",
      {
        method: "POST",
        body: { message, conversation_id: conversationId },
        authenticated: true,
      },
    ),

  /** Get user profile. */
  getProfile: () =>
    request<{ display_name: string; email: string }>("/me", {
      authenticated: true,
    }),

  /** Get conversation history. */
  getHistory: (page = 1) =>
    request<{ conversations: unknown[] }>(`/me/history?page=${page}`, {
      authenticated: true,
    }),

  /** Export user data. */
  exportData: () =>
    request<Blob>("/me/export", { authenticated: true }),

  /** Delete account (GDPR). */
  deleteAccount: () =>
    request<void>("/me", { method: "DELETE", authenticated: true }),
};

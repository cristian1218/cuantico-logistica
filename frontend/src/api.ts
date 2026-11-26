import { SearchResponse, ToolCall } from "./types";

const API_BASE = "http://127.0.0.1:8000/api";

export async function sendChatMessage(
  token: string,
  message: string
): Promise<{ answer: string; tool_calls: ToolCall[] }> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ message }),
  });

  const body = await res.json();
  if (!res.ok) {
    const errorMsg = body?.error?.message || `Error HTTP ${res.status}`;
    throw new Error(errorMsg);
  }

  return body;
}

export async function searchDeliveries(
  token: string,
  query: string
): Promise<SearchResponse> {
  const url = `${API_BASE}/deliveries/search?q=${encodeURIComponent(query)}`;
  const res = await fetch(url, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  const body = await res.json();
  if (!res.ok) {
    const errorMsg = body?.error?.message || `Error HTTP ${res.status}`;
    throw new Error(errorMsg);
  }

  return body;
}

export async function checkBackendHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(2000) });
    return res.ok;
  } catch {
    return false;
  }
}

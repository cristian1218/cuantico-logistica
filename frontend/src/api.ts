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

export interface IngestResponse {
  status: number;
  duplicate: boolean;
  delivery?: Record<string, any>;
  error?: { code: string; message: string; details?: any };
}

export async function ingestDeliveryEvent(
  token: string,
  eventData: Record<string, any>
): Promise<IngestResponse> {
  const res = await fetch(`${API_BASE}/events`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(eventData),
  });

  const body = await res.json();
  return {
    status: res.status,
    duplicate: Boolean(body?.duplicate),
    delivery: body?.delivery,
    error: body?.error,
  };
}

export interface BackendStatus {
  online: boolean;
  llmConnected: boolean;
  llmModel: string;
}

export async function checkBackendStatus(): Promise<BackendStatus> {
  try {
    const res = await fetch(`${API_BASE}/status`, { signal: AbortSignal.timeout(2000) });
    if (!res.ok) {
      return { online: false, llmConnected: false, llmModel: "" };
    }
    const body = await res.json();
    return {
      online: true,
      llmConnected: Boolean(body?.llm_connected),
      llmModel: body?.llm_model || "",
    };
  } catch {
    return { online: false, llmConnected: false, llmModel: "" };
  }
}

export async function checkBackendHealth(): Promise<boolean> {
  const status = await checkBackendStatus();
  return status.online;
}

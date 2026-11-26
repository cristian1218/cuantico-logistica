export interface ToolCall {
  name: string;
  args: Record<string, unknown>;
  result: {
    status?: string;
    data?: Record<string, unknown>;
    error?: { code: string; message: string };
  };
}

export interface ChatMessage {
  id: string;
  sender: "user" | "assistant";
  text: string;
  toolCalls?: ToolCall[];
  timestamp: string;
}

export interface DeliveryHit {
  delivery_id: string;
  merchant_id: string;
  merchant_name: string;
  courier_id: string;
  courier_name: string | null;
  address: string | null;
  status: string;
  cost_status: string;
  cost_cents: number | null;
  currency: string;
}

export interface SearchResponse {
  query: string;
  count: number;
  results: DeliveryHit[];
}

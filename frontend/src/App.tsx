import React, { useState, useEffect } from "react";
import "./App.css";
import { Header } from "./components/Header";
import { ChatView } from "./components/ChatView";
import { SearchView } from "./components/SearchView";
import { IngestView } from "./components/IngestView";
import { sendChatMessage, checkBackendHealth } from "./api";
import { ChatMessage } from "./types";

export const App: React.FC = () => {
  const [token, setToken] = useState<string>("tok-ops-admin");
  const [activeTab, setActiveTab] = useState<"chat" | "ingest" | "search">("chat");
  const [backendOnline, setBackendOnline] = useState<boolean>(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const check = async () => {
      const ok = await checkBackendHealth();
      setBackendOnline(ok);
    };
    check();
    const interval = setInterval(check, 8000);
    return () => clearInterval(interval);
  }, []);

  const handleSendMessage = async (text: string) => {
    const userMsg: ChatMessage = {
      id: `usr-${Date.now()}`,
      sender: "user",
      text,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);
    setError(null);

    try {
      const resp = await sendChatMessage(token, text);
      const assistantMsg: ChatMessage = {
        id: `ast-${Date.now()}`,
        sender: "assistant",
        text: resp.answer,
        toolCalls: resp.tool_calls,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleClearChat = () => {
    setMessages([]);
    setError(null);
  };

  return (
    <div className="app-root">
      <Header token={token} onTokenChange={setToken} backendOnline={backendOnline} />

      <nav className="tab-navigation">
        <button
          type="button"
          className={`tab-btn ${activeTab === "chat" ? "active" : ""}`}
          onClick={() => setActiveTab("chat")}
        >
          Asistente Conversacional
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === "ingest" ? "active" : ""}`}
          onClick={() => setActiveTab("ingest")}
        >
          Ingesta de Eventos (POST)
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === "search" ? "active" : ""}`}
          onClick={() => setActiveTab("search")}
        >
          Buscador de Entregas (REST)
        </button>
      </nav>

      <main className="app-main">
        {activeTab === "chat" && (
          <ChatView
            messages={messages}
            loading={loading}
            error={error}
            onSendMessage={handleSendMessage}
            onClearChat={handleClearChat}
          />
        )}
        {activeTab === "ingest" && <IngestView token={token} />}
        {activeTab === "search" && <SearchView token={token} />}
      </main>
    </div>
  );
};

export default App;

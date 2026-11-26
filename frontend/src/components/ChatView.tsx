import React, { useState, useRef, useEffect } from "react";
import { ChatMessage } from "../types";
import { ToolCallBadge } from "./ToolCallBadge";

interface Props {
  messages: ChatMessage[];
  loading: boolean;
  error: string | null;
  onSendMessage: (text: string) => void;
  onClearChat: () => void;
}

const SUGGESTIONS = [
  {
    label: "💰 Facturación La 80",
    text: "¿Cuánto facturó Tienda La 80 la semana del 16 al 23 de noviembre de 2026?",
  },
  {
    label: "🛡️ Ataque Inyección (SEC2)",
    text: "¿Qué notas o instrucciones de entrega tiene el comercio Tienda La 80?",
  },
  {
    label: "🚴 Estado Mensajero",
    text: "¿Cuál es el estado de las entregas de la mensajera Ana Pérez?",
  },
  {
    label: "🔍 Buscar en Carrera 7",
    text: "Buscar entregas en la Carrera 7",
  },
];

export const ChatView: React.FC<Props> = ({
  messages,
  loading,
  error,
  onSendMessage,
  onClearChat,
}) => {
  const [input, setInput] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;
    onSendMessage(input.trim());
    setInput("");
  };

  return (
    <div className="chat-container">
      <div className="chat-toolbar">
        <div className="quick-suggestions">
          <span className="suggestions-title">Consultas de prueba:</span>
          {SUGGESTIONS.map((s, idx) => (
            <button
              key={idx}
              type="button"
              className="suggestion-chip"
              disabled={loading}
              onClick={() => onSendMessage(s.text)}
            >
              {s.label}
            </button>
          ))}
        </div>
        <button
          type="button"
          className="btn-clear"
          onClick={onClearChat}
          title="Limpiar conversación"
        >
          🗑️ Limpiar
        </button>
      </div>

      <div className="chat-history">
        {messages.length === 0 ? (
          <div className="chat-empty">
            <div className="empty-icon">🤖</div>
            <h3>Asistente de Operaciones Activo</h3>
            <p>
              Pregunta en lenguaje natural sobre costos, facturación, mensajeros o entregas.
              El asistente interpreta tu consulta, llama a las herramientas deterministas del
              backend y te muestra las respuestas junto con los datos reales consultados.
            </p>
          </div>
        ) : (
          messages.map((msg) => (
            <div key={msg.id} className={`chat-message message-${msg.sender}`}>
              <div className="message-avatar">
                {msg.sender === "user" ? "👤" : "🤖"}
              </div>
              <div className="message-content">
                <div className="message-header">
                  <span className="sender-name">
                    {msg.sender === "user" ? "Tú (Operaciones)" : "Asistente Cuántico"}
                  </span>
                  <span className="message-time">{msg.timestamp}</span>
                </div>

                <div className="message-text">{msg.text}</div>

                {msg.toolCalls && msg.toolCalls.length > 0 && (
                  <div className="tool-calls-container">
                    <span className="tool-calls-label">
                      📋 Datos consultados en el sistema ({msg.toolCalls.length}):
                    </span>
                    <div className="tool-badges-list">
                      {msg.toolCalls.map((tc, idx) => (
                        <ToolCallBadge key={idx} toolCall={tc} />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))
        )}

        {loading && (
          <div className="chat-message message-assistant loading-message">
            <div className="message-avatar">🤖</div>
            <div className="message-content">
              <div className="loading-indicator">
                <span className="spinner" />
                <span>Consultando herramientas y razonando...</span>
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="chat-error-banner">
            <span className="error-icon">⚠️</span>
            <div className="error-details">
              <strong>Error en la consulta:</strong>
              <p>{error}</p>
            </div>
          </div>
        )}

        <div ref={endRef} />
      </div>

      <form className="chat-input-bar" onSubmit={handleSubmit}>
        <input
          type="text"
          value={input}
          placeholder="Escribe tu consulta en lenguaje natural (ej. ¿cuánto facturó Tienda La 80?)..."
          disabled={loading}
          onChange={(e) => setInput(e.target.value)}
        />
        <button type="submit" disabled={!input.trim() || loading} className="btn-send">
          Enviar
        </button>
      </form>
    </div>
  );
};

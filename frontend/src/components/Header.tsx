import React from "react";

interface Props {
  token: string;
  onTokenChange: (token: string) => void;
  backendOnline: boolean;
  llmConnected: boolean;
  llmModel: string;
  isResponding?: boolean;
}

export const Header: React.FC<Props> = ({
  token,
  onTokenChange,
  backendOnline,
  llmConnected,
  llmModel,
  isResponding,
}) => {
  return (
    <header className="app-header">
      <div className="header-brand">
        <div className="brand-text">
          <h1>Cuántico Logística</h1>
          <span className="brand-divider">/</span>
          <span className="subtitle">Control de Operaciones y Liquidación</span>
        </div>
      </div>

      <div className="header-controls">
        <div className="system-status-indicator">
          <span className={`status-dot ${backendOnline ? "online" : "offline"}`} />
          <span className="status-label">{backendOnline ? "API :8000 activa" : "API desconectada"}</span>
        </div>

        <div className="system-status-indicator llm-status-indicator">
          {isResponding ? (
            <>
              <span className="status-dot active" />
              <span className="status-label">Gemini respondiendo...</span>
            </>
          ) : llmConnected ? (
            <>
              <span className="status-dot online" />
              <span className="status-label">{llmModel ? `${llmModel} conectado` : "Gemini conectado"}</span>
            </>
          ) : (
            <>
              <span className="status-dot warning" />
              <span className="status-label">Modo offline (Mock LLM)</span>
            </>
          )}
        </div>

        <div className="token-control">
          <label htmlFor="token-select">Rol / Alcance:</label>
          <select
            id="token-select"
            value={token}
            onChange={(e) => onTokenChange(e.target.value)}
          >
            <option value="tok-ops-admin">Admin Operaciones (Acceso Global)</option>
            <option value="tok-la80-001">Operador Tienda La 80 (Acotado)</option>
            <option value="tok-cafe-001">Operador Café Central (Acotado)</option>
          </select>
        </div>
      </div>
    </header>
  );
};

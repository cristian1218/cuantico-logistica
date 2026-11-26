import React from "react";

interface Props {
  token: string;
  onTokenChange: (token: string) => void;
  backendOnline: boolean;
}

export const Header: React.FC<Props> = ({ token, onTokenChange, backendOnline }) => {
  return (
    <header className="app-header">
      <div className="header-brand">
        <span className="brand-logo">📦</span>
        <div>
          <h1>Cuántico Logística</h1>
          <p className="subtitle">Asistente de Operaciones y Control de Entregas</p>
        </div>
      </div>

      <div className="header-controls">
        <div className="status-pill">
          <span className={`status-dot ${backendOnline ? "online" : "offline"}`} />
          <span>{backendOnline ? "API Online (8000)" : "API No Conectada"}</span>
        </div>

        <div className="token-control">
          <label htmlFor="token-select">Rol / Alcance:</label>
          <select
            id="token-select"
            value={token}
            onChange={(e) => onTokenChange(e.target.value)}
          >
            <option value="tok-ops-admin">👑 Admin Operaciones (Alcance Global)</option>
            <option value="tok-la80-001">🏪 Operador Tienda La 80 (Acotado)</option>
            <option value="tok-cafe-001">☕ Operador Café Central (Acotado)</option>
          </select>
        </div>
      </div>
    </header>
  );
};

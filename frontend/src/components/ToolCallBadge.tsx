import React, { useState } from "react";
import { ToolCall } from "../types";

interface Props {
  toolCall: ToolCall;
}

export const ToolCallBadge: React.FC<Props> = ({ toolCall }) => {
  const [open, setOpen] = useState(false);
  const isError = toolCall.result.status === "error";

  return (
    <div className={`tool-badge ${isError ? "tool-badge-error" : "tool-badge-ok"}`}>
      <button
        type="button"
        className="tool-badge-header"
        onClick={() => setOpen(!open)}
        title="Clic para inspeccionar datos devueltos por el sistema determinista"
      >
        <span className="tool-icon">{isError ? "⚠️" : "⚙️"}</span>
        <span className="tool-name">{toolCall.name}</span>
        <span className="tool-status">{isError ? "Rechazado" : "Consultado"}</span>
        <span className="tool-toggle">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="tool-badge-body">
          <div className="tool-section">
            <strong>Argumentos enviados por el modelo:</strong>
            <pre>{JSON.stringify(toolCall.args, null, 2)}</pre>
          </div>
          <div className="tool-section">
            <strong>Resultado determinista del backend:</strong>
            <pre>{JSON.stringify(toolCall.result, null, 2)}</pre>
          </div>
        </div>
      )}
    </div>
  );
};

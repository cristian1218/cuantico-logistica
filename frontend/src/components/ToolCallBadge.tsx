import React, { useState } from "react";
import { ToolCall } from "../types";

interface Props {
  toolCall: ToolCall;
}

const TOOL_DEFINITIONS: Record<string, { label: string; icon: string }> = {
  get_merchant_totals: { label: "Facturación y Totales de Comercio", icon: "📊" },
  get_merchant_info: { label: "Información y Notas del Comercio", icon: "ℹ️" },
  get_courier_status: { label: "Entregas por Mensajero", icon: "🚴" },
  search_deliveries: { label: "Búsqueda Segura de Entregas", icon: "🔍" },
  get_delivery_detail: { label: "Detalle de Entrega y Costeo", icon: "📦" },
};

const ARG_TRANSLATIONS: Record<string, string> = {
  merchant_id: "Comercio",
  from_date: "Fecha desde",
  to_date: "Fecha hasta",
  courier_id: "Mensajero",
  query: "Término de búsqueda",
  delivery_id: "ID de entrega",
};

const formatCOP = (cents: number | null | undefined): string => {
  if (cents === null || cents === undefined) return "Pendiente";
  return `$${(cents / 100).toLocaleString("es-CO", { minimumFractionDigits: 2 })} COP`;
};

const formatDate = (isoStr: string | null | undefined): string => {
  if (!isoStr) return "—";
  try {
    const d = new Date(isoStr);
    return d.toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return String(isoStr);
  }
};

export const ToolCallBadge: React.FC<Props> = ({ toolCall }) => {
  const [open, setOpen] = useState(false);
  const [showRawJson, setShowRawJson] = useState(false);
  const isError = toolCall.result.status === "error";

  const def = TOOL_DEFINITIONS[toolCall.name] || {
    label: toolCall.name,
    icon: "⚙️",
  };

  const renderArgsInSpanish = () => {
    const entries = Object.entries(toolCall.args);
    if (entries.length === 0) return <em>Sin argumentos</em>;

    return (
      <div className="tool-kv-grid">
        {entries.map(([key, val]) => (
          <div key={key} className="tool-kv-row">
            <span className="tool-kv-label">{ARG_TRANSLATIONS[key] || key}:</span>
            <span className="tool-kv-val">
              {key.includes("date") ? formatDate(String(val)) : String(val)}
            </span>
          </div>
        ))}
      </div>
    );
  };

  const renderDataInSpanish = () => {
    if (isError) {
      const err = (toolCall.result.error || { message: "Error desconocido" }) as Record<string, any>;
      return (
        <div className="tool-error-alert">
          <strong>⚠️ {err.code ? `[${err.code}] ` : ""}Operación rechazada:</strong>
          <p>{err.message}</p>
        </div>
      );
    }

    const data = (toolCall.result.data || {}) as Record<string, any>;
    if (!toolCall.result.data) {
      return <em>No se recibieron datos</em>;
    }

    switch (toolCall.name) {
      case "get_merchant_totals":
        return (
          <div className="tool-kv-grid">
            <div className="tool-kv-row">
              <span className="tool-kv-label">Comercio:</span>
              <span className="tool-kv-val font-semibold">
                {String(data.merchant_name)} ({String(data.merchant_id)})
              </span>
            </div>
            <div className="tool-kv-row">
              <span className="tool-kv-label">Período consultado:</span>
              <span className="tool-kv-val">
                {formatDate(data.from)} — {formatDate(data.to)}
              </span>
            </div>
            <div className="tool-kv-row highlight-row">
              <span className="tool-kv-label">Total facturado:</span>
              <span className="tool-kv-val text-success font-bold">
                {formatCOP(data.total_cents)}
              </span>
            </div>
            <div className="tool-kv-row">
              <span className="tool-kv-label">Entregas totales:</span>
              <span className="tool-kv-val">{String(data.deliveries)}</span>
            </div>
            <div className="tool-kv-row">
              <span className="tool-kv-label">Entregadas con éxito:</span>
              <span className="tool-kv-val">{String(data.delivered)}</span>
            </div>
            <div className="tool-kv-row">
              <span className="tool-kv-label">Entregas fallidas:</span>
              <span className="tool-kv-val">{String(data.failed)}</span>
            </div>
            {Number(data.pending_cost_deliveries) > 0 && (
              <div className="tool-kv-row text-warning">
                <span className="tool-kv-label">Pendientes de costeo:</span>
                <span className="tool-kv-val">{String(data.pending_cost_deliveries)}</span>
              </div>
            )}
          </div>
        );

      case "get_merchant_info":
        return (
          <div className="tool-kv-grid">
            <div className="tool-kv-row">
              <span className="tool-kv-label">Comercio:</span>
              <span className="tool-kv-val font-semibold">
                {String(data.merchant_name)} ({String(data.merchant_id)})
              </span>
            </div>
            <div className="tool-kv-row">
              <span className="tool-kv-label">Zona horaria:</span>
              <span className="tool-kv-val">{String(data.timezone)}</span>
            </div>
            <div className="tool-kv-row">
              <span className="tool-kv-label">Tarifa base:</span>
              <span className="tool-kv-val">{formatCOP(data.base_fee_cents)}</span>
            </div>
            <div className="tool-kv-row">
              <span className="tool-kv-label">Recargo por km:</span>
              <span className="tool-kv-val">{formatCOP(data.per_km_cents)}</span>
            </div>
            {Boolean(data.notes) && (
              <div className="tool-untrusted-box">
                <div className="untrusted-header">
                  🛡️ Notas del comercio (Dato no confiable — SEC2)
                </div>
                <div className="untrusted-content">{String(data.notes)}</div>
              </div>
            )}
          </div>
        );

      case "get_courier_status":
        return (
          <div className="tool-kv-grid">
            <div className="tool-kv-row">
              <span className="tool-kv-label">Mensajero:</span>
              <span className="tool-kv-val font-semibold">{String(data.courier_id)}</span>
            </div>
            <div className="tool-kv-row">
              <span className="tool-kv-label">Total asignadas:</span>
              <span className="tool-kv-val">{String(data.total)}</span>
            </div>
            <div className="tool-kv-row">
              <span className="tool-kv-label">Por estado:</span>
              <div className="status-badges-wrap">
                {Object.entries((data.by_status as Record<string, number>) || {}).map(([st, cnt]) => (
                  <span key={st} className={`status-tag status-${st}`}>
                    {st}: {String(cnt)}
                  </span>
                ))}
              </div>
            </div>
          </div>
        );

      case "search_deliveries":
        return (
          <div className="tool-kv-grid">
            <div className="tool-kv-row">
              <span className="tool-kv-label">Texto buscado:</span>
              <span className="tool-kv-val">"{String(data.query)}"</span>
            </div>
            <div className="tool-kv-row">
              <span className="tool-kv-label">Coincidencias encontradas:</span>
              <span className="tool-kv-val font-semibold">{String(data.count)}</span>
            </div>
            {Array.isArray(data.results) && data.results.length > 0 && (
              <div className="tool-mini-results">
                {data.results.slice(0, 5).map((r: any) => (
                  <div key={r.delivery_id} className="mini-result-item">
                    <code>{r.delivery_id}</code> — <strong>{r.merchant_name}</strong> (
                    {r.courier_name || r.courier_id || "Sin mensajero"}) |{" "}
                    <span className={`status-tag status-${r.status}`}>{r.status}</span> |{" "}
                    {formatCOP(r.cost_cents)}
                  </div>
                ))}
                {data.results.length > 5 && (
                  <small className="text-muted">
                    ... y {data.results.length - 5} resultados más.
                  </small>
                )}
              </div>
            )}
          </div>
        );

      case "get_delivery_detail":
        return (
          <div className="tool-kv-grid">
            <div className="tool-kv-row">
              <span className="tool-kv-label">Entrega:</span>
              <span className="tool-kv-val font-semibold">{String(data.delivery_id)}</span>
            </div>
            <div className="tool-kv-row">
              <span className="tool-kv-label">Comercio:</span>
              <span className="tool-kv-val">{String(data.merchant_id)}</span>
            </div>
            <div className="tool-kv-row">
              <span className="tool-kv-label">Mensajero:</span>
              <span className="tool-kv-val">{String(data.courier_id || "—")}</span>
            </div>
            <div className="tool-kv-row">
              <span className="tool-kv-label">Dirección:</span>
              <span className="tool-kv-val">{String(data.address || "—")}</span>
            </div>
            <div className="tool-kv-row">
              <span className="tool-kv-label">Estado:</span>
              <span className={`status-tag status-${data.status}`}>{String(data.status)}</span>
            </div>
            <div className="tool-kv-row highlight-row">
              <span className="tool-kv-label">Costo liquidado:</span>
              <span className="tool-kv-val text-success font-bold">
                {formatCOP(data.cost_cents)}
              </span>
            </div>
            {Boolean(data.breakdown) && (
              <div className="tool-breakdown-box">
                <span className="tool-kv-label">Desglose de costos:</span>
                <ul>
                  <li>Tarifa base: {formatCOP(data.breakdown.base_fee_cents)}</li>
                  {data.breakdown.distance_cents !== undefined && (
                    <li>
                      Recargo distancia ({data.breakdown.distance_meters} m):{" "}
                      {formatCOP(data.breakdown.distance_cents)}
                    </li>
                  )}
                  {Number(data.breakdown.night_surcharge_cents) > 0 && (
                    <li>
                      Recargo nocturno (15%): {formatCOP(data.breakdown.night_surcharge_cents)}
                    </li>
                  )}
                  {Boolean(data.breakdown.failure_discount_percent) && (
                    <li>
                      Descuento por fallo: {data.breakdown.failure_discount_percent}% de la tarifa
                      base
                    </li>
                  )}
                </ul>
              </div>
            )}
            {Array.isArray(data.anomalies) && data.anomalies.length > 0 && (
              <div className="tool-anomalies-box">
                <strong>Anomalías registradas:</strong>
                <ul>
                  {data.anomalies.map((a: string, i: number) => (
                    <li key={i}>{a}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        );

      default:
        return <pre>{JSON.stringify(data, null, 2)}</pre>;
    }
  };

  return (
    <div className={`tool-badge ${isError ? "tool-badge-error" : "tool-badge-ok"}`}>
      <button
        type="button"
        className="tool-badge-header"
        onClick={() => setOpen(!open)}
        title="Clic para desplegar los datos consultados por el sistema"
      >
        <span className="tool-icon">{isError ? "⚠️" : def.icon}</span>
        <span className="tool-name">
          {def.label} <small className="tool-technical-name">({toolCall.name})</small>
        </span>
        <span className="tool-status">{isError ? "Rechazado" : "Consultado con éxito"}</span>
        <span className="tool-toggle">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="tool-badge-body">
          <div className="tool-section">
            <span className="tool-section-title">Parámetros de consulta:</span>
            {renderArgsInSpanish()}
          </div>

          <div className="tool-section">
            <div className="tool-section-header-row">
              <span className="tool-section-title">Respuesta del sistema:</span>
              <button
                type="button"
                className="btn-toggle-json"
                onClick={() => setShowRawJson(!showRawJson)}
              >
                {showRawJson ? "👁️ Ocultar JSON técnico" : "📄 Ver JSON técnico"}
              </button>
            </div>

            {showRawJson ? (
              <pre className="raw-json-block">{JSON.stringify(toolCall.result, null, 2)}</pre>
            ) : (
              <div className="tool-friendly-card">{renderDataInSpanish()}</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

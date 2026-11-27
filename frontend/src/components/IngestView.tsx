import React, { useState } from "react";
import { ingestDeliveryEvent, IngestResponse } from "../api";

interface Props {
  token: string;
}

interface Scenario {
  id: string;
  title: string;
  badge: string;
  desc: string;
  payload: Record<string, any>;
}

const formatCOP = (cents: number | null | undefined): string => {
  if (cents === null || cents === undefined) return "Pendiente de costeo";
  return `$${(cents / 100).toLocaleString("es-CO", { minimumFractionDigits: 2 })} COP`;
};

const SCENARIOS: Scenario[] = [
  {
    id: "sc-1",
    title: "1. Crear Entrega",
    badge: "Flujo Inicial",
    desc: "Crea el evento inicial para Tienda La 80. Costo inicial queda en estado pendiente.",
    payload: {
      event_id: `ev-creada-${Date.now().toString().slice(-4)}`,
      delivery_id: `d-demo-${Date.now().toString().slice(-4)}`,
      merchant_id: "m-la80",
      courier_id: "c-ana",
      type: "creada",
      occurred_at: "2026-11-26T14:00:00Z",
      address: "Calle 80 # 15-20, Bogotá",
    },
  },
  {
    id: "sc-2",
    title: "2. Recogida con GPS",
    badge: "Geolocalización",
    desc: "Registra que Ana recogió el paquete en portería con coordenadas lat/lon.",
    payload: {
      event_id: `ev-recogida-${Date.now().toString().slice(-4)}`,
      delivery_id: "d-la80-01",
      merchant_id: "m-la80",
      courier_id: "c-ana",
      type: "recogida",
      occurred_at: "2026-11-26T14:30:00Z",
      lat: 4.6097,
      lon: -74.0817,
    },
  },
  {
    id: "sc-3",
    title: "3. Entrega Nocturna (15%)",
    badge: "Recargo 15%",
    desc: "Entrega completada a las 22:45 hora local. Liquida distancia + 15% nocturno.",
    payload: {
      event_id: `ev-nocturna-${Date.now().toString().slice(-4)}`,
      delivery_id: "d-la80-01",
      merchant_id: "m-la80",
      courier_id: "c-ana",
      type: "entregada",
      occurred_at: "2026-11-26T22:45:00Z",
      lat: 4.6534,
      lon: -74.0543,
    },
  },
  {
    id: "sc-4",
    title: "4. Entrega Fallida (40%)",
    badge: "Regla R6 (40%)",
    desc: "No pudo ser entregada. Cobra exactamente el 40% de tarifa base sin recargos.",
    payload: {
      event_id: `ev-fallida-${Date.now().toString().slice(-4)}`,
      delivery_id: `d-fallida-${Date.now().toString().slice(-4)}`,
      merchant_id: "m-la80",
      courier_id: "c-pedro",
      type: "fallida",
      occurred_at: "2026-11-26T16:15:00Z",
    },
  },
  {
    id: "sc-5",
    title: "5. Idempotencia (Duplicado)",
    badge: "HTTP 200 Idempotente",
    desc: "Mismo event_id. Debe responder HTTP 200 con duplicate: true sin alterar costos.",
    payload: {
      event_id: "ev-001",
      delivery_id: "d-la80-01",
      merchant_id: "m-la80",
      courier_id: "c-ana",
      type: "creada",
      occurred_at: "2026-11-18T14:00:00Z",
      address: "Calle 80 # 11-42",
    },
  },
  {
    id: "sc-6",
    title: "6. Conflicto de Idempotencia",
    badge: "HTTP 409 Conflict",
    desc: "Mismo event_id con datos distintos. El sistema rechaza atómicamente con 409.",
    payload: {
      event_id: "ev-001",
      delivery_id: "d-la80-01",
      merchant_id: "m-la80",
      courier_id: "c-ana",
      type: "fallida",
      occurred_at: "2026-11-18T14:00:00Z",
    },
  },
  {
    id: "sc-7",
    title: "7. Aislamiento Multi-tenant",
    badge: "HTTP 403 Forbidden",
    desc: "Intenta registrar evento para Tienda La 80 con token de Café Central (rechazo 403).",
    payload: {
      event_id: `ev-sec3-${Date.now().toString().slice(-4)}`,
      delivery_id: "d-sec3-test",
      merchant_id: "m-la80",
      courier_id: "c-ana",
      type: "creada",
      occurred_at: "2026-11-26T17:00:00Z",
    },
  },
];

export const IngestView: React.FC<Props> = ({ token }) => {
  const [selectedScenario, setSelectedScenario] = useState<Scenario>(SCENARIOS[0]);
  const [jsonText, setJsonText] = useState<string>(
    JSON.stringify(SCENARIOS[0].payload, null, 2)
  );
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<IngestResponse | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);
  const [showRawResponse, setShowRawResponse] = useState(false);

  const handleSelectScenario = (sc: Scenario) => {
    setSelectedScenario(sc);
    setJsonText(JSON.stringify(sc.payload, null, 2));
    setParseError(null);
    setResponse(null);
  };

  const handleSend = async () => {
    setParseError(null);
    setLoading(true);
    let parsed: Record<string, any>;
    try {
      parsed = JSON.parse(jsonText);
    } catch (err: unknown) {
      setParseError(err instanceof Error ? err.message : "JSON inválido");
      setLoading(false);
      return;
    }

    try {
      const res = await ingestDeliveryEvent(token, parsed);
      setResponse(res);
    } catch (err: unknown) {
      setResponse({
        status: 500,
        duplicate: false,
        error: {
          code: "network_error",
          message: err instanceof Error ? err.message : String(err),
        },
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="ingest-view">
      <div className="ingest-header">
        <h2>Simulador Visual de Ingesta (POST /api/events)</h2>
        <p>
          Simula y audita en vivo la recepción de eventos, el cálculo determinista de costos, la
          idempotencia ante reintentos y el control de acceso multi-tenant sin necesidad de Swagger o cURL.
        </p>

        <div className="scenarios-bar">
          <span className="scenarios-title">Escenarios operativos preconfigurados:</span>
          <div className="scenarios-chips">
            {SCENARIOS.map((sc) => (
              <button
                key={sc.id}
                type="button"
                className={`scenario-chip ${selectedScenario.id === sc.id ? "active" : ""}`}
                onClick={() => handleSelectScenario(sc)}
              >
                <span className="chip-badge">{sc.badge}</span>
                <span className="chip-title">{sc.title}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="ingest-grid">
        <div className="ingest-editor-card">
          <div className="editor-card-header">
            <div>
              <strong>Payload del evento HTTP</strong>
              <small className="scenario-desc">{selectedScenario.desc}</small>
            </div>
            <button
              type="button"
              className="btn-reset-scenario"
              onClick={() => setJsonText(JSON.stringify(selectedScenario.payload, null, 2))}
            >
              Restaurar plantilla
            </button>
          </div>

          <textarea
            className="json-editor-textarea"
            rows={12}
            value={jsonText}
            onChange={(e) => {
              setJsonText(e.target.value);
              setParseError(null);
            }}
          />

          {parseError && (
            <div className="json-error-banner">
              Error de sintaxis JSON: {parseError}
            </div>
          )}

          <div className="editor-actions">
            <button
              type="button"
              className="btn-send-event"
              disabled={loading}
              onClick={handleSend}
            >
              {loading ? "Enviando evento..." : "Enviar evento (POST /api/events)"}
            </button>
            <span className="auth-hint">
              Token de autorización enviado en cabecera: <code>{token}</code>
            </span>
          </div>
        </div>

        <div className="ingest-result-card">
          <div className="editor-card-header">
            <strong>Respuesta del backend</strong>
            {response && (
              <button
                type="button"
                className="btn-toggle-json"
                onClick={() => setShowRawResponse(!showRawResponse)}
              >
                {showRawResponse ? "Ver resumen" : "Ver JSON crudo"}
              </button>
            )}
          </div>

          {!response && (
            <div className="result-placeholder">
              <h4>Esperando envío de evento</h4>
              <p>
                Selecciona uno de los escenarios preconfigurados o edita el payload, y presiona{" "}
                <strong>Enviar evento</strong> para inspeccionar la respuesta, código HTTP y cálculo de costos.
              </p>
            </div>
          )}

          {response && showRawResponse && (
            <pre className="raw-response-block">{JSON.stringify(response, null, 2)}</pre>
          )}

          {response && !showRawResponse && (
            <div className="result-content">
              <div className="http-status-row">
                <span className="status-label">Código HTTP:</span>
                <span
                  className={`http-badge ${
                    response.status === 201
                      ? "http-201"
                      : response.status === 200
                      ? "http-200"
                      : "http-error"
                  }`}
                >
                  {response.status}{" "}
                  {response.status === 201
                    ? "Created"
                    : response.status === 200
                    ? "OK (Duplicado)"
                    : response.status === 403
                    ? "Forbidden"
                    : response.status === 409
                    ? "Conflict"
                    : "Error"}
                </span>
              </div>

              {response.duplicate && (
                <div className="duplicate-alert">
                  <strong>Idempotencia detectada:</strong> Este evento ya había sido procesado previamente.
                  El sistema devuelve el estado actual sin duplicar cobros ni recargos.
                </div>
              )}

              {response.error && (
                <div className="error-result-alert">
                  <strong>[{response.error.code}]:</strong> {response.error.message}
                </div>
              )}

              {response.delivery && (
                <div className="delivery-card">
                  <div className="delivery-card-title">
                    Estado derivado de la entrega: <code>{response.delivery.delivery_id}</code>
                  </div>

                  <div className="tool-kv-grid">
                    <div className="tool-kv-row">
                      <span className="tool-kv-label">Comercio:</span>
                      <span className="tool-kv-val font-semibold">
                        {response.delivery.merchant_id}
                      </span>
                    </div>
                    <div className="tool-kv-row">
                      <span className="tool-kv-label">Mensajero:</span>
                      <span className="tool-kv-val">{response.delivery.courier_id || "—"}</span>
                    </div>
                    <div className="tool-kv-row">
                      <span className="tool-kv-label">Estado actual:</span>
                      <span className={`status-tag status-${response.delivery.status}`}>
                        {response.delivery.status}
                      </span>
                    </div>
                    <div className="tool-kv-row highlight-row">
                      <span className="tool-kv-label">Costo liquidado:</span>
                      <span className="tool-kv-val text-success font-bold">
                        {formatCOP(response.delivery.cost_cents)}
                      </span>
                    </div>
                    {response.delivery.address && (
                      <div className="tool-kv-row">
                        <span className="tool-kv-label">Dirección:</span>
                        <span className="tool-kv-val">{response.delivery.address}</span>
                      </div>
                    )}
                  </div>

                  {response.delivery.breakdown && (
                    <div className="tool-breakdown-box">
                      <span className="tool-kv-label font-semibold">Desglose matemático:</span>
                      <ul>
                        <li>Tarifa base: {formatCOP(response.delivery.breakdown.base_fee_cents)}</li>
                        {response.delivery.breakdown.distance_cents !== undefined && (
                          <li>
                            Recargo distancia ({response.delivery.breakdown.distance_meters} m):{" "}
                            {formatCOP(response.delivery.breakdown.distance_cents)}
                          </li>
                        )}
                        {Number(response.delivery.breakdown.night_surcharge_cents) > 0 && (
                          <li className="text-warning">
                            Recargo nocturno (15%):{" "}
                            {formatCOP(response.delivery.breakdown.night_surcharge_cents)}
                          </li>
                        )}
                        {Boolean(response.delivery.breakdown.failure_discount_percent) && (
                          <li className="text-warning">
                            Cobro por fallo: {response.delivery.breakdown.failure_discount_percent}%
                            de la tarifa base
                          </li>
                        )}
                      </ul>
                    </div>
                  )}

                  {Array.isArray(response.delivery.anomalies) &&
                    response.delivery.anomalies.length > 0 && (
                      <div className="tool-anomalies-box">
                        <strong>Anomalías registradas:</strong>
                        <ul>
                          {response.delivery.anomalies.map((a: string, i: number) => (
                            <li key={i}>{a}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

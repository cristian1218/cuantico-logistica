import React, { useState } from "react";
import { searchDeliveries } from "../api";
import { DeliveryHit } from "../types";

interface Props {
  token: string;
}

export const SearchView: React.FC<Props> = ({ token }) => {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<DeliveryHit[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const resp = await searchDeliveries(token, query.trim());
      setResults(resp.results);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
      setResults(null);
    } finally {
      setLoading(false);
    }
  };

  const testPayloads = [
    { label: "Búsqueda normal: 'Reforma'", val: "Reforma" },
    { label: "Búsqueda normal: 'La 80'", val: "La 80" },
    { label: "Test Inyección SQL: ' OR 1=1 --", val: "' OR 1=1 --" },
    { label: "Test Comodines LIKE: '%'", val: "%" },
  ];

  return (
    <div className="search-view">
      <div className="search-header">
        <h2>Buscador de Entregas (Seguro & Parametrizado)</h2>
        <p>
          Búsqueda directa sobre entregas, comercios, mensajeros y direcciones. Los caracteres
          comodín y las comillas se escapan y se consultan vía parámetros enlazados (SEC1).
        </p>

        <div className="test-payloads">
          <span className="payloads-title">Verificación de seguridad (Mitigación SEC1):</span>
          {testPayloads.map((tp, idx) => (
            <button
              key={idx}
              type="button"
              className="suggestion-chip"
              onClick={() => {
                setQuery(tp.val);
              }}
            >
              {tp.label}
            </button>
          ))}
        </div>

        <form onSubmit={handleSearch} className="search-form">
          <input
            type="text"
            value={query}
            placeholder="Buscar por comercio, dirección o payload SQL..."
            onChange={(e) => setQuery(e.target.value)}
          />
          <button type="submit" disabled={!query.trim() || loading} className="btn-send">
            {loading ? "Buscando..." : "Buscar"}
          </button>
        </form>
      </div>

      {error && (
        <div className="chat-error-banner">
          <div>
            <strong>Error en la búsqueda:</strong>
            <p>{error}</p>
          </div>
        </div>
      )}

      {results !== null && (
        <div className="search-results">
          <div className="results-count">
            Resultados encontrados: <strong>{results.length}</strong>
          </div>

          {results.length === 0 ? (
            <div className="no-results">
              No se encontraron coincidencias para la búsqueda dentro del alcance del usuario.
            </div>
          ) : (
            <div className="results-table-wrapper">
              <table className="results-table">
                <thead>
                  <tr>
                    <th>ID Entrega</th>
                    <th>Comercio</th>
                    <th>Mensajero</th>
                    <th>Dirección</th>
                    <th>Estado</th>
                    <th>Costo</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((r) => (
                    <tr key={r.delivery_id}>
                      <td><code>{r.delivery_id}</code></td>
                      <td>{r.merchant_name}</td>
                      <td>{r.courier_name || r.courier_id}</td>
                      <td>{r.address || "—"}</td>
                      <td>
                        <span className={`status-tag status-${r.status}`}>
                          {r.status}
                        </span>
                      </td>
                      <td>
                        {r.cost_cents !== null
                          ? `$${(r.cost_cents / 100).toLocaleString("es-CO", { minimumFractionDigits: 2 })} COP`
                          : "Pendiente"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

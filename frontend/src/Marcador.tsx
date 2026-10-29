/**
 * Componente de marcado (check-in/out) con GPS y QR.
 * Validación server-side de geocerca.
 */
import { useState } from "react";
import { api } from "./api";
import { QrScanner } from "./QrScanner";

interface MarcadorProps {
  token: string;
}

export function Marcador({ token }: MarcadorProps) {
  const [tipo, setTipo] = useState<"entrada" | "salida">("entrada");
  const [loading, setLoading] = useState(false);
  const [resultado, setResultado] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [showQr, setShowQr] = useState(false);

  const marcarGps = async () => {
    setLoading(true);
    setError(null);
    setResultado(null);

    try {
      const position = await new Promise<GeolocationPosition>((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, {
          enableHighAccuracy: true,
          timeout: 10000
        });
      });

      const resp = await api("/marcas/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          tipo,
          lat: position.coords.latitude,
          lng: position.coords.longitude,
          ts_cliente: new Date().toISOString()
        })
      });

      const data = await resp.json();

      if (!resp.ok) {
        throw new Error(data.detail || "Error al registrar marca");
      }

      setResultado(data);
    } catch (err: any) {
      setError(err.message || "Error al obtener ubicación");
    } finally {
      setLoading(false);
    }
  };

  const onQrScan = async (code: string) => {
    setShowQr(false);
    setLoading(true);
    setError(null);

    try {
      const resp = await api("/marcas/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          tipo,
          qr_code: code,
          ts_cliente: new Date().toISOString()
        })
      });

      const data = await resp.json();

      if (!resp.ok) {
        throw new Error(data.detail || "Error al registrar marca");
      }

      setResultado(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: "1rem", maxWidth: "500px", margin: "0 auto" }}>
      <h2>Registrar Asistencia</h2>

      <div style={{ marginBottom: "1rem" }}>
        <label style={{ display: "block", marginBottom: "0.5rem" }}>
          Tipo de marca:
        </label>
        <div>
          <label style={{ marginRight: "1rem" }}>
            <input
              type="radio"
              checked={tipo === "entrada"}
              onChange={() => setTipo("entrada")}
            />
            {" "}Entrada
          </label>
          <label>
            <input
              type="radio"
              checked={tipo === "salida"}
              onChange={() => setTipo("salida")}
            />
            {" "}Salida
          </label>
        </div>
      </div>

      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
        <button
          onClick={marcarGps}
          disabled={loading}
          style={{
            flex: 1,
            padding: "1rem",
            fontSize: "1rem",
            backgroundColor: "#007bff",
            color: "#fff",
            border: "none",
            borderRadius: "4px",
            cursor: loading ? "not-allowed" : "pointer"
          }}
        >
          📍 Marcar con GPS
        </button>

        <button
          onClick={() => setShowQr(true)}
          disabled={loading}
          style={{
            flex: 1,
            padding: "1rem",
            fontSize: "1rem",
            backgroundColor: "#28a745",
            color: "#fff",
            border: "none",
            borderRadius: "4px",
            cursor: loading ? "not-allowed" : "pointer"
          }}
        >
          📷 Escanear QR
        </button>
      </div>

      {loading && (
        <div style={{
          padding: "1rem",
          backgroundColor: "#f0f0f0",
          borderRadius: "4px",
          textAlign: "center"
        }}>
          Registrando...
        </div>
      )}

      {error && (
        <div style={{
          padding: "1rem",
          backgroundColor: "#f8d7da",
          color: "#721c24",
          borderRadius: "4px",
          marginBottom: "1rem"
        }}>
          ⚠️ {error}
        </div>
      )}

      {resultado && (
        <div style={{
          padding: "1rem",
          backgroundColor: resultado.validacion_estado === "ok" ? "#d4edda" : "#fff3cd",
          color: resultado.validacion_estado === "ok" ? "#155724" : "#856404",
          borderRadius: "4px"
        }}>
          <h3 style={{ margin: "0 0 0.5rem 0" }}>
            {resultado.validacion_estado === "ok" ? "✅ Marca registrada" : "⚠️ Marca con alerta"}
          </h3>
          <p style={{ margin: "0.25rem 0" }}>
            <strong>Hora servidor:</strong> {new Date(resultado.ts_servidor).toLocaleString("es-PE")}
          </p>
          {resultado.distancia_m != null && (
            <p style={{ margin: "0.25rem 0" }}>
              <strong>Distancia:</strong> {Math.round(resultado.distancia_m)} metros de la sede
            </p>
          )}
          {resultado.validacion_estado === "fuera_geocerca" && (
            <p style={{ margin: "0.5rem 0 0 0", fontSize: "0.9rem" }}>
              La marca fue registrada pero está fuera del radio de la geocerca.
              Su supervisor será notificado.
            </p>
          )}
        </div>
      )}

      {showQr && <QrScanner onScan={onQrScan} onClose={() => setShowQr(false)} />}
    </div>
  );
}

/**
 * Componente de marcado (check-in/out) con GPS y QR.
 * Validación server-side de geocerca. Sin red, la marca se guarda en la cola offline (IndexedDB)
 * y se sincroniza al volver la conexión (Sprint 3 / Inc 5).
 */
import { useEffect, useState } from "react";
import { api } from "./api";
import { QrScanner } from "./QrScanner";
import { alCambiar, autoSincronizar, descartar, encolar, enviarApi, listar, MarcaPendiente, sincronizar, uuid } from "./offlineQueue";

interface MarcadorProps {
  token: string;
}

const esErrorDeRed = (e: any) => e instanceof TypeError || e?.message === "Failed to fetch" || e?.message === "NetworkError when attempting to fetch resource.";

export function Marcador({ token }: MarcadorProps) {
  const [tipo, setTipo] = useState<"entrada" | "salida">("entrada");
  const [loading, setLoading] = useState(false);
  const [resultado, setResultado] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [showQr, setShowQr] = useState(false);
  const [cola, setCola] = useState<MarcaPendiente[]>([]);
  const [online, setOnline] = useState(navigator.onLine);

  useEffect(() => {
    const refrescar = () => { listar().then(setCola).catch(() => setCola([])); };
    const on = () => setOnline(true), off = () => setOnline(false);
    window.addEventListener("online", on); window.addEventListener("offline", off);
    const quitar = alCambiar(refrescar);
    const parar = autoSincronizar(enviarApi);
    refrescar();
    return () => { quitar(); parar(); window.removeEventListener("online", on); window.removeEventListener("offline", off); };
  }, []);

  /** Envía online con UUID idempotente; si no hay red, encola la marca (ts del dispositivo). */
  const registrar = async (datos: { lat?: number; lng?: number; qr_code?: string }) => {
    const marca = { id_idempotente: uuid(), tipo, ts_cliente: new Date().toISOString(), ...datos };
    const guardarOffline = async () => {
      await encolar(marca);
      setAviso("Sin conexión: la marca quedó guardada en este dispositivo y se enviará al volver la red (quedará como diferida).");
    };
    if (!navigator.onLine) return guardarOffline();
    try {
      const data = await api("/marcas/", { method: "POST", headers: { Authorization: `Bearer ${token}` }, body: marca });
      setResultado(data);
    } catch (err: any) {
      if (esErrorDeRed(err)) return guardarOffline();
      throw err;
    }
  };

  const ejecutar = async (fn: () => Promise<void>, porDefecto: string) => {
    setLoading(true); setError(null); setResultado(null); setAviso(null);
    try { await fn(); } catch (err: any) {
      const msg = String(err?.message || "");
      setError(msg.includes("User denied Geolocation") ? "Debe permitir el acceso a la ubicación" : msg || porDefecto);
    } finally { setLoading(false); }
  };

  const marcarGps = () => ejecutar(async () => {
    const position = await new Promise<GeolocationPosition>((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: true, timeout: 10000 });
    });
    await registrar({ lat: position.coords.latitude, lng: position.coords.longitude });
  }, "Error al obtener ubicación");

  const onQrScan = (code: string) => { setShowQr(false); ejecutar(() => registrar({ qr_code: code }), "Error al escanear código QR"); };

  const pendientes = cola.filter(m => m.estado === "pendiente");
  const rechazadas = cola.filter(m => m.estado === "rechazada");
  const btn = (bg: string) => ({ flex: 1, padding: "1rem", fontSize: "1rem", backgroundColor: bg, color: "#fff", border: "none", borderRadius: "4px", cursor: loading ? "not-allowed" : "pointer" });
  const caja = (bg: string, color: string) => ({ padding: "1rem", backgroundColor: bg, color, borderRadius: "4px", marginBottom: "1rem" });

  return (
    <div style={{ padding: "1rem", maxWidth: "500px", margin: "0 auto" }}>
      <h2>Registrar Asistencia</h2>
      {!online && <div data-testid="sin-red" style={caja("#e2e3e5", "#383d41")}>Sin conexión. Puede marcar igual: se guardará en el dispositivo.</div>}

      <div style={{ marginBottom: "1rem" }}>
        <label style={{ display: "block", marginBottom: "0.5rem" }}>Tipo de marca:</label>
        <div>
          <label style={{ marginRight: "1rem" }}><input type="radio" checked={tipo === "entrada"} onChange={() => setTipo("entrada")} /> Entrada</label>
          <label><input type="radio" checked={tipo === "salida"} onChange={() => setTipo("salida")} /> Salida</label>
        </div>
      </div>

      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
        <button onClick={marcarGps} disabled={loading} style={btn("#007bff")}>📍 Marcar con GPS</button>
        <button onClick={() => setShowQr(true)} disabled={loading} style={btn("#28a745")}>📷 Escanear QR</button>
      </div>

      {loading && <div style={caja("#f0f0f0", "#000")}>Registrando...</div>}
      {error && <div style={caja("#f8d7da", "#721c24")}>⚠️ {error}</div>}
      {aviso && <div style={caja("#cce5ff", "#004085")}>📥 {aviso}</div>}

      {resultado && (
        <div style={caja(resultado.validacion_estado === "ok" ? "#d4edda" : "#fff3cd", resultado.validacion_estado === "ok" ? "#155724" : "#856404")}>
          <h3 style={{ margin: "0 0 0.5rem 0" }}>{resultado.validacion_estado === "ok" ? "✅ Marca registrada" : "⚠️ Marca con alerta"}</h3>
          <p style={{ margin: "0.25rem 0" }}><strong>Hora servidor:</strong> {new Date(resultado.ts_servidor).toLocaleString("es-PE")}</p>
          {resultado.distancia_m != null && <p style={{ margin: "0.25rem 0" }}><strong>Distancia:</strong> {Math.round(resultado.distancia_m)} metros de la sede</p>}
          {resultado.validacion_estado === "fuera_geocerca" && (
            <p style={{ margin: "0.5rem 0 0 0", fontSize: "0.9rem" }}>La marca fue registrada pero está fuera del radio de la geocerca. Su supervisor será notificado.</p>
          )}
        </div>
      )}

      {(pendientes.length > 0 || rechazadas.length > 0) && (
        <div data-testid="cola-offline" style={caja("#fff8e1", "#5d4200")}>
          <strong>Marcas por sincronizar: {pendientes.length}</strong>
          {pendientes.length > 0 && <button style={{ marginLeft: 8 }} disabled={!online} onClick={() => sincronizar(enviarApi).catch(() => {})}>Reintentar ahora</button>}
          <ul style={{ margin: "0.5rem 0 0 1rem", padding: 0 }}>
            {cola.map(m => (
              <li key={m.id_idempotente}>
                {m.tipo} {new Date(m.ts_cliente).toLocaleString("es-PE")} ({m.qr_code ? "QR" : "GPS"}) —{" "}
                {m.estado === "pendiente" ? `pendiente${m.intentos ? ` (${m.intentos} intentos)` : ""}` : (
                  <span style={{ color: "#b00" }}>rechazada: {m.error} <button onClick={() => descartar(m.id_idempotente)}>Descartar</button></span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {showQr && <QrScanner onScan={onQrScan} onClose={() => setShowQr(false)} />}
    </div>
  );
}
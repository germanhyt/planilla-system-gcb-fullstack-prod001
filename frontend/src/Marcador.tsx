/**
 * Componente de marcado (check-in/out) con GPS y QR.
 * Validación server-side de geocerca. Sin red, la marca se guarda en la cola offline (IndexedDB)
 * y se sincroniza al volver la conexión (Sprint 3 / Inc 5).
 */
import { useEffect, useState } from "react";
import { CheckCircle2, CloudOff, Fingerprint, Loader2, LogIn, LogOut, MapPin, QrCode, RefreshCw, TriangleAlert, Wifi } from "lucide-react";
import { Aviso, Button, Card, Pill, cn } from "./ui";
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
  const [ahora, setAhora] = useState(new Date());
  useEffect(() => { const h = setInterval(() => setAhora(new Date()), 1000); return () => clearInterval(h); }, []);
  const gps = typeof navigator !== "undefined" && "geolocation" in navigator;
  const okRes = resultado?.validacion_estado === "ok";

  return (
    <section className="pantalla mx-auto flex w-full max-w-md flex-col gap-4">
      <h2 className="!m-0 text-xl font-semibold tracking-tight">Registrar Asistencia</h2>
      <div className="flex flex-wrap gap-2">
        {online ? <Pill tono="success"><Wifi size={12} />En línea</Pill> : <Pill tono="neutral"><CloudOff size={12} />Sin conexión</Pill>}
        <Pill tono={gps ? "accent" : "warning"}><MapPin size={12} />{gps ? "GPS disponible" : "GPS no disponible"}</Pill>
        <Pill tono={pendientes.length ? "warning" : "neutral"}><RefreshCw size={12} />{pendientes.length} pendiente(s)</Pill>
      </div>
      {!online && <div data-testid="sin-red"><Aviso tono="neutral">Sin conexión. Puede marcar igual: se guardará en el dispositivo.</Aviso></div>}

      <Card className="flex flex-col items-center gap-5 py-8 text-center">
        <div>
          <div className="text-4xl font-bold tabular-nums tracking-tight">{ahora.toLocaleTimeString("es-PE", { timeZone: "America/Lima", hour: "2-digit", minute: "2-digit", second: "2-digit" })}</div>
          <div className="text-sm capitalize text-muted">{ahora.toLocaleDateString("es-PE", { timeZone: "America/Lima", weekday: "long", day: "numeric", month: "long" })}</div>
        </div>
        <div role="radiogroup" aria-label="Tipo de marca" className="grid w-full grid-cols-2 gap-1 rounded-card bg-surface-2 p-1">
          {(["entrada", "salida"] as const).map(t => <label key={t} className={cn("flex cursor-pointer items-center justify-center gap-2 rounded-ctl py-2.5 text-sm font-semibold capitalize", tipo === t ? "bg-primary text-primary-fg shadow" : "text-muted")}>
            <input type="radio" className="sr-only" checked={tipo === t} onChange={() => setTipo(t)} />{t === "entrada" ? <LogIn size={16} /> : <LogOut size={16} />}{t === "entrada" ? "Entrada" : "Salida"}</label>)}
        </div>
        <button type="button" onClick={marcarGps} disabled={loading} aria-label="Marcar con GPS"
          className="grid size-44 cursor-pointer place-items-center rounded-full border-0 bg-gradient-to-br from-accent-strong to-primary text-white shadow-[0_12px_40px_-8px_var(--c-accent)] ring-8 ring-accent-soft transition active:scale-95 disabled:cursor-not-allowed disabled:opacity-70">
          <span className="flex flex-col items-center gap-1.5">{loading ? <Loader2 size={44} className="animate-spin" /> : <Fingerprint size={48} />}
            <span className="text-base font-semibold">{loading ? "Registrando…" : "Marcar con GPS"}</span><span className="text-xs capitalize opacity-80">{tipo}</span></span>
        </button>
        <Button icon={QrCode} onClick={() => setShowQr(true)} disabled={loading} className="w-full justify-center">Escanear QR</Button>
      </Card>

      {error && <Aviso tono="danger"><TriangleAlert size={14} className="mr-1 inline" />{error}</Aviso>}
      {aviso && <Aviso tono="accent">{aviso}</Aviso>}

      {resultado && (
        <Card className={cn("border-l-4", okRes ? "border-l-success" : "border-l-warning")}>
          <p className="m-0 mb-2 flex items-center gap-2 font-semibold">{okRes ? <CheckCircle2 className="text-success" size={20} /> : <TriangleAlert className="text-warning" size={20} />}{okRes ? "Marca registrada" : "Marca con alerta"}</p>
          <p className="m-0 text-sm"><strong>Hora servidor:</strong> {new Date(resultado.ts_servidor).toLocaleString("es-PE")}</p>
          {resultado.distancia_m != null && <p className="m-0 text-sm"><strong>Distancia:</strong> {Math.round(resultado.distancia_m)} metros de la sede</p>}
          {resultado.validacion_estado === "fuera_geocerca" && <p className="m-0 mt-2 text-sm text-muted">La marca fue registrada pero está fuera del radio de la geocerca. Su supervisor será notificado.</p>}
        </Card>
      )}

      {(pendientes.length > 0 || rechazadas.length > 0) && (
        <Card data-testid="cola-offline">
          <div className="flex items-center justify-between gap-2"><strong className="text-sm">Marcas por sincronizar: {pendientes.length}</strong>
            {pendientes.length > 0 && <Button size="sm" icon={RefreshCw} disabled={!online} onClick={() => sincronizar(enviarApi).catch(() => {})}>Reintentar ahora</Button>}</div>
          <ul className="m-0 mt-2 grid list-none gap-1.5 p-0 text-sm">
            {cola.map(m => (
              <li key={m.id_idempotente} className="flex flex-wrap items-center gap-2 rounded-ctl bg-surface-2 px-2 py-1.5">
                <span className="capitalize">{m.tipo}</span> <span className="text-muted">{new Date(m.ts_cliente).toLocaleString("es-PE")} ({m.qr_code ? "QR" : "GPS"})</span>
                {m.estado === "pendiente" ? <Pill tono="warning">pendiente{m.intentos ? ` (${m.intentos} intentos)` : ""}</Pill> : (
                  <><Pill tono="danger">rechazada: {m.error}</Pill><Button size="sm" onClick={() => descartar(m.id_idempotente)}>Descartar</Button></>
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {showQr && <QrScanner onScan={onQrScan} onClose={() => setShowQr(false)} />}
    </section>
  );
}

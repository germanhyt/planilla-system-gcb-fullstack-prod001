/**
 * QR Scanner con fallback para iOS Safari (zxing-js/browser).
 * BarcodeDetector no está disponible en iOS, usamos zxing como polyfill.
 */
import { useEffect, useRef, useState } from "react";

interface QrScannerProps {
  onScan: (code: string) => void;
  onClose: () => void;
}

export function QrScanner({ onScan, onClose }: QrScannerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);

  useEffect(() => {
    let animationId: number;
    let detector: any = null;

    const startScanning = async () => {
      try {
        const mediaStream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "environment" }
        });
        
        if (videoRef.current) {
          videoRef.current.srcObject = mediaStream;
          setStream(mediaStream);
          await videoRef.current.play();

          if ("BarcodeDetector" in window) {
            detector = new (window as any).BarcodeDetector({
              formats: ["qr_code"]
            });
            
            const detectQr = async () => {
              if (videoRef.current && videoRef.current.readyState === videoRef.current.HAVE_ENOUGH_DATA) {
                try {
                  const barcodes = await detector.detect(videoRef.current);
                  if (barcodes.length > 0) {
                    onScan(barcodes[0].rawValue);
                    return;
                  }
                } catch (e) {
                  console.error("Error detectando QR:", e);
                }
              }
              animationId = requestAnimationFrame(detectQr);
            };
            
            detectQr();
          } else {
            const { BrowserMultiFormatReader } = await import("@zxing/browser");
            const codeReader = new BrowserMultiFormatReader();
            
            const scanFromVideo = async () => {
              if (videoRef.current && videoRef.current.readyState === videoRef.current.HAVE_ENOUGH_DATA) {
                try {
                  const result = await codeReader.decodeFromVideoElement(videoRef.current);
                  if (result) {
                    onScan(result.getText());
                    return;
                  }
                } catch (e) {
                }
              }
              animationId = requestAnimationFrame(scanFromVideo);
            };
            
            scanFromVideo();
          }
        }
      } catch (err: any) {
        setError("No se pudo acceder a la cámara: " + err.message);
      }
    };

    startScanning();

    return () => {
      if (animationId) {
        cancelAnimationFrame(animationId);
      }
      if (stream) {
        stream.getTracks().forEach(track => track.stop());
      }
    };
  }, [onScan]);

  return (
    <div style={{
      position: "fixed",
      top: 0,
      left: 0,
      width: "100%",
      height: "100%",
      backgroundColor: "#000",
      zIndex: 1000,
      display: "flex",
      flexDirection: "column"
    }}>
      <div style={{ padding: "1rem", backgroundColor: "#333", color: "#fff" }}>
        <button onClick={onClose} style={{ float: "right" }}>✕ Cerrar</button>
        <h3 style={{ margin: 0 }}>Escanear código QR</h3>
      </div>
      
      {error && (
        <div style={{ padding: "1rem", backgroundColor: "#f44", color: "#fff" }}>
          {error}
        </div>
      )}
      
      <video
        ref={videoRef}
        style={{
          flex: 1,
          width: "100%",
          objectFit: "cover"
        }}
        playsInline
        muted
      />
      
      <div style={{
        position: "absolute",
        top: "50%",
        left: "50%",
        transform: "translate(-50%, -50%)",
        width: "250px",
        height: "250px",
        border: "3px solid rgba(255,255,255,0.6)",
        borderRadius: "12px",
        pointerEvents: "none"
      }} />
    </div>
  );
}

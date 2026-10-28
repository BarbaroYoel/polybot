import { useCallback, useEffect, useRef, useState } from "react";
import { openInterpreter, parseInterpreterEvent } from "../../lib/api/interpreter";
import type { InterpreterEvent } from "../../lib/api/interpreter";
import { RecordingError, VoiceRecorder, resample, toPcm } from "../../lib/audio/recorder";

export type InterpreterStatus =
  | "idle"
  | "connecting"
  | "listening"
  | "processing"
  | "stopped"
  | "error";

export interface InterpreterLine {
  id: string;
  text: string;
  translation: string | null;
  language: string | null;
  startMs: number;
  endMs: number;
}

const TARGET_RATE = 16_000;
/** Half a second at 16 kHz: the server's window feeder groups these into ~1 s chunks. */
const FRAME_SAMPLES = 8_000;
const STOP_TIMEOUT_MS = 8_000;

function recordingMessage(error: unknown): string {
  if (error instanceof RecordingError) {
    if (error.kind === "denied") {
      return "No tenemos permiso para usar el micrófono. Revisá los permisos del navegador para este sitio.";
    }
    if (error.kind === "unsupported") {
      return "Este navegador no puede grabar audio.";
    }
    return "No encontramos un micrófono disponible. Revisá que esté conectado y vuelve a intentar.";
  }
  return "No pudimos acceder al micrófono. Revisá los permisos del navegador y vuelve a intentar.";
}

/**
 * One live interpreter session (F7 T5, ADR-022).
 *
 * The hook owns the WebSocket and the microphone: it buffers the browser's float blocks into
 * 0.5 s PCM frames, sends them, and turns the server events into the ephemeral history the screen
 * paints. Nothing is stored; closing the tab or the session drops everything (P2).
 */
export function useInterpreter() {
  const [status, setStatus] = useState<InterpreterStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [permissionDenied, setPermissionDenied] = useState(false);
  const [partialText, setPartialText] = useState("");
  const [partialPending, setPartialPending] = useState("");
  const [partialTranslation, setPartialTranslation] = useState("");
  const [segments, setSegments] = useState<InterpreterLine[]>([]);

  const socketRef = useRef<WebSocket | null>(null);
  const recorderRef = useRef<VoiceRecorder | null>(null);
  const pendingRef = useRef<Float32Array>(new Float32Array(0));
  const statusRef = useRef<InterpreterStatus>("idle");
  const stopRequestedRef = useRef(false);
  const cancelRequestedRef = useRef(false);
  const captureStartedRef = useRef(false);
  const stopTimerRef = useRef<number | null>(null);

  const updateStatus = useCallback((next: InterpreterStatus) => {
    statusRef.current = next;
    setStatus(next);
  }, []);

  const queueAudio = useCallback((samples: Float32Array, rate: number, socket: WebSocket) => {
    if (socket.readyState !== WebSocket.OPEN) return;
    const resampled = resample(samples, rate, TARGET_RATE);
    if (resampled.length === 0) return;

    const merged = new Float32Array(pendingRef.current.length + resampled.length);
    merged.set(pendingRef.current);
    merged.set(resampled, pendingRef.current.length);

    let offset = 0;
    while (merged.length - offset >= FRAME_SAMPLES) {
      try {
        socket.send(toPcm(merged.subarray(offset, offset + FRAME_SAMPLES)));
      } catch {
        // The socket closed between the readyState check and send; the close handler cleans up.
        return;
      }
      offset += FRAME_SAMPLES;
    }
    pendingRef.current = merged.slice(offset);
  }, []);

  const start = useCallback(
    async (source: string | null, target: string) => {
      if (socketRef.current || recorderRef.current) return;

      setError(null);
      setPermissionDenied(false);
      setPartialText("");
      setPartialPending("");
      setPartialTranslation("");
      setSegments([]);
      pendingRef.current = new Float32Array(0);
      stopRequestedRef.current = false;
      cancelRequestedRef.current = false;
      captureStartedRef.current = false;
      updateStatus("connecting");

      let socket: WebSocket;
      try {
        socket = openInterpreter(source, target);
      } catch {
        setError("No pudimos abrir la conexión del intérprete. Revisá que la API esté corriendo.");
        updateStatus("error");
        return;
      }
      socketRef.current = socket;
      socket.binaryType = "arraybuffer";

      const finish = () => {
        if (socketRef.current !== socket) return;
        if (stopTimerRef.current !== null) {
          window.clearTimeout(stopTimerRef.current);
          stopTimerRef.current = null;
        }
        socketRef.current = null;
        const recorder = recorderRef.current;
        recorderRef.current = null;
        if (recorder) void recorder.cancel();

        if (cancelRequestedRef.current || stopRequestedRef.current) {
          updateStatus("stopped");
        } else if (statusRef.current !== "error") {
          setError("La conexión con el intérprete se cerró. Volvé a iniciar la sesión.");
          updateStatus("error");
        }
      };

      const beginCapture = async () => {
        if (captureStartedRef.current || stopRequestedRef.current) return;
        captureStartedRef.current = true;
        const recorder = new VoiceRecorder();
        recorderRef.current = recorder;
        try {
          await recorder.start((samples, rate) => {
            const current = socketRef.current;
            if (current) queueAudio(samples, rate, current);
          });
          if (stopRequestedRef.current || socketRef.current !== socket) {
            await recorder.cancel();
            return;
          }
          updateStatus("listening");
        } catch (caught: unknown) {
          recorderRef.current = null;
          setPermissionDenied(caught instanceof RecordingError && caught.kind === "denied");
          setError(recordingMessage(caught));
          updateStatus("error");
          try {
            socket.send(JSON.stringify({ type: "cancel" }));
          } catch {
            // The socket may already be closed; the close handler finishes the session.
          }
          socket.close();
        }
      };

      const handleEvent = (event: InterpreterEvent) => {
        switch (event.type) {
          case "ready":
            void beginCapture();
            break;
          case "partial":
            setPartialText(event.text);
            setPartialPending(event.pending);
            break;
          case "partial_translation":
            setPartialTranslation(event.text);
            break;
          case "segment":
            setSegments((current) => [
              ...current,
              {
                id: event.id,
                text: event.text,
                translation: null,
                language: event.language,
                startMs: event.start_ms,
                endMs: event.end_ms,
              },
            ]);
            setPartialText("");
            setPartialPending("");
            setPartialTranslation("");
            break;
          case "translation":
            setSegments((current) =>
              current.map((line) =>
                line.id === event.segment_id ? { ...line, translation: event.text } : line,
              ),
            );
            break;
          case "error":
            setError(event.error.message);
            if (event.error.code === "stt_unavailable" || event.error.code === "internal_error") {
              updateStatus("error");
            }
            break;
        }
      };

      socket.onmessage = (message) => {
        if (typeof message.data !== "string") return;
        const event = parseInterpreterEvent(message.data);
        if (event) handleEvent(event);
      };
      socket.onerror = () => {
        if (!stopRequestedRef.current && !cancelRequestedRef.current) {
          setError("No pudimos conectar con el intérprete. Revisá que la API esté corriendo.");
          updateStatus("error");
        }
      };
      socket.onclose = () => finish();
    },
    [queueAudio, updateStatus],
  );

  const stop = useCallback(() => {
    const recorder = recorderRef.current;
    recorderRef.current = null;
    if (recorder) void recorder.cancel();

    const socket = socketRef.current;
    if (!socket) {
      updateStatus("stopped");
      return;
    }
    if (socket.readyState === WebSocket.CONNECTING) {
      stopRequestedRef.current = true;
      socket.close();
      updateStatus("stopped");
      return;
    }
    if (socket.readyState !== WebSocket.OPEN) {
      updateStatus("stopped");
      return;
    }

    stopRequestedRef.current = true;
    updateStatus("processing");
    if (pendingRef.current.length > 0) {
      try {
        socket.send(toPcm(pendingRef.current));
      } catch {
        // The close handler finishes the session; the pending tail is not worth another state.
      }
      pendingRef.current = new Float32Array(0);
    }
    socket.send(JSON.stringify({ type: "stop" }));

    if (stopTimerRef.current !== null) window.clearTimeout(stopTimerRef.current);
    stopTimerRef.current = window.setTimeout(() => {
      stopTimerRef.current = null;
      try {
        socket.close();
      } catch {
        // Already closed.
      }
    }, STOP_TIMEOUT_MS);
  }, [updateStatus]);

  const cancel = useCallback(() => {
    cancelRequestedRef.current = true;
    const recorder = recorderRef.current;
    recorderRef.current = null;
    if (recorder) void recorder.cancel();

    const socket = socketRef.current;
    if (socket) {
      try {
        if (socket.readyState === WebSocket.OPEN) {
          socket.send(JSON.stringify({ type: "cancel" }));
        }
      } catch {
        // The close below is enough.
      }
      socket.close();
    }
    socketRef.current = null;
    setPartialText("");
    setPartialPending("");
    setPartialTranslation("");
    updateStatus("stopped");
  }, [updateStatus]);

  useEffect(() => {
    return () => {
      const recorder = recorderRef.current;
      if (recorder) void recorder.cancel();
      socketRef.current?.close();
      if (stopTimerRef.current !== null) window.clearTimeout(stopTimerRef.current);
    };
  }, []);

  return {
    status,
    error,
    permissionDenied,
    partialText,
    partialPending,
    partialTranslation,
    segments,
    start,
    stop,
    cancel,
  };
}

/**
 * Voice input for the chat composer (F4 S5, S6, S7).
 *
 * The screen states are the ones desing.md §6.1.2 asks for: «Escuchando…» while the microphone is
 * open, «Transcribiendo…» while the clip travels, and a visible error with a recovery action. The
 * transcript is handed to the composer as text — it is never sent: the user reads it, edits it and
 * sends it (S6).
 *
 * The recording is stopped by the contract limit, not by a hidden timer in the recorder: the hook
 * owns the timeout and the copy that explains it.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage } from "../../lib/api/client";
import { transcribe } from "../../lib/api/voice";
import { MAX_RECORDING_MS, RecordingError, VoiceRecorder } from "../../lib/audio/recorder";

export type VoiceStatus = "idle" | "recording" | "transcribing";

export interface VoiceError {
  message: string;
  /**
   * `permissions` offers «Reintentar micrófono» after the user enables the permission in the
   * browser; anything else offers «Reintentar» for the failed request.
   */
  kind: "permissions" | "failure";
}

interface UseVoiceInputOptions {
  /** The conversation's language: the engine transcribes that language and detects it otherwise. */
  languageCode?: string;
  /** Appends the transcript to the composer; the user still decides when to send it. */
  onTranscript: (text: string) => void;
}

const PERMISSION_MESSAGE =
  "No tenemos permiso para usar el micrófono. Abrí los permisos del sitio en el navegador (el ícono junto a la dirección), habilitá el micrófono y volvé a intentar.";

export function useVoiceInput({ languageCode, onTranscript }: UseVoiceInputOptions) {
  const recorderRef = useRef<VoiceRecorder | null>(null);
  const clipRef = useRef<Blob | null>(null);
  const mountedRef = useRef(true);
  const [status, setStatus] = useState<VoiceStatus>("idle");
  const [error, setError] = useState<VoiceError | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      // Leaving the screen must release the microphone: the browser keeps the indicator otherwise.
      void recorderRef.current?.cancel();
      recorderRef.current = null;
    };
  }, []);

  const send = useCallback(
    async (clip: Blob) => {
      clipRef.current = clip;
      setStatus("transcribing");
      setError(null);
      setNotice(null);
      try {
        const result = await transcribe(clip, languageCode);
        if (!mountedRef.current) return;
        const text = result.text.trim();
        if (text === "") {
          // Silence is a valid answer from the engine, not a failure (contract §3).
          setNotice("No se escuchó nada. Probá de nuevo, un poco más cerca del micrófono.");
        } else {
          onTranscript(text);
        }
        setStatus("idle");
      } catch (failure) {
        if (!mountedRef.current) return;
        setError({
          message: errorMessage(failure, "No pudimos transcribir el audio. Vuelve a intentar."),
          kind: "failure",
        });
        setStatus("idle");
      }
    },
    [languageCode, onTranscript],
  );

  const stop = useCallback(async () => {
    const recorder = recorderRef.current;
    if (!recorder) return;
    recorderRef.current = null;
    const recording = await recorder.stop();
    if (!recording) {
      setStatus("idle");
      return;
    }
    if (recording.autoStopped) {
      setNotice("La grabación se cortó a los 2 minutos: es el máximo por mensaje.");
    }
    await send(recording.blob);
  }, [send]);

  const start = useCallback(async () => {
    if (recorderRef.current) return;
    const recorder = new VoiceRecorder();
    recorderRef.current = recorder;
    setError(null);
    setNotice(null);
    try {
      await recorder.start();
      if (!mountedRef.current) {
        await recorder.cancel();
        return;
      }
      setStatus("recording");
    } catch (caught) {
      recorderRef.current = null;
      await recorder.cancel();
      if (!mountedRef.current) return;
      setStatus("idle");
      if (caught instanceof RecordingError) {
        setError({
          message: caught.kind === "denied" ? PERMISSION_MESSAGE : caught.message,
          kind: caught.kind === "denied" ? "permissions" : "failure",
        });
        return;
      }
      setError({
        message: "No pudimos abrir el micrófono. Vuelve a intentar.",
        kind: "failure",
      });
    }
  }, []);

  const cancel = useCallback(async () => {
    const recorder = recorderRef.current;
    recorderRef.current = null;
    await recorder?.cancel();
    setStatus("idle");
    setNotice(null);
  }, []);

  /** The same clip again: the audio was fine, the request was not. */
  const retry = useCallback(async () => {
    const clip = clipRef.current;
    if (!clip) return;
    await send(clip);
  }, [send]);

  // The contract limit is a screen concern: stop the recorder and explain why the clip ended.
  useEffect(() => {
    if (status !== "recording") return;
    const id = window.setTimeout(() => {
      void stop();
    }, MAX_RECORDING_MS);
    return () => window.clearTimeout(id);
  }, [status, stop]);

  return { status, error, notice, start, stop, cancel, retry, dismissNotice: () => setNotice(null) };
}

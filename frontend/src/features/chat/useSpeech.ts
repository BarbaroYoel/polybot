/**
 * Playing one tutor message out loud (F4 S5; desing.md §6.1.2, §8).
 *
 * The clip is synthesized once per message and kept in memory, so «Más lento» replays the same
 * audio at a lower rate instead of asking the backend again — and `Escuchar` never blocks the chat
 * while the engine speaks.
 *
 * One rule from the design document drives the states: the user must always see whether the app is
 * playing something («Reproduciendo…»), and stopping must leave the screen in the same place.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage } from "../../lib/api/client";
import { synthesizeSpeech } from "../../lib/api/speech";

export type SpeechStatus = "idle" | "loading" | "playing" | "error";

interface UseSpeechOptions {
  text: string;
  /** The conversation's language: the voice is chosen from it (S3). */
  languageCode?: string;
}

export function useSpeech({ text, languageCode }: UseSpeechOptions) {
  const [status, setStatus] = useState<SpeechStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const clipRef = useRef<Blob | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const urlRef = useRef<string | null>(null);

  const release = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.onended = null;
      audioRef.current.onerror = null;
      audioRef.current.pause();
      audioRef.current = null;
    }
    if (urlRef.current) {
      URL.revokeObjectURL(urlRef.current);
      urlRef.current = null;
    }
  }, []);

  // Leaving the bubble (or the screen) must stop the audio: otherwise it keeps playing silently.
  useEffect(() => release, [release]);

  const stop = useCallback(() => {
    release();
    setStatus("idle");
  }, [release]);

  const play = useCallback(
    async (speed: number) => {
      if (status === "playing") {
        stop();
        return;
      }
      if (!languageCode) {
        setError("Esta conversación no tiene un idioma configurado.");
        setStatus("error");
        return;
      }

      setError(null);
      try {
        let blob = clipRef.current;
        if (!blob) {
          setStatus("loading");
          const clip = await synthesizeSpeech({ text, languageCode });
          blob = clip.blob;
          clipRef.current = blob;
        }

        release();
        const url = URL.createObjectURL(blob);
        urlRef.current = url;
        const audio = new Audio(url);
        // The same clip, slower: synthesis is not repeated for «Más lento» (S4).
        audio.playbackRate = speed;
        audio.onended = () => {
          release();
          setStatus("idle");
        };
        audio.onerror = () => {
          release();
          setError("No pudimos reproducir el audio. Vuelve a intentar.");
          setStatus("error");
        };
        audioRef.current = audio;
        setStatus("playing");
        await audio.play();
      } catch (failure) {
        release();
        setStatus("error");
        setError(errorMessage(failure, "No pudimos generar el audio. Vuelve a intentar."));
      }
    },
    [languageCode, release, status, stop, text],
  );

  return { status, error, play, stop };
}

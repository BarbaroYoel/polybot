/**
 * Recording a clip in the browser for `POST /voice/transcribe` (F4 S5, S6, S7).
 *
 * No dependency is added: `getUserMedia` + `AudioContext` + a small WAV encoder is all the PWA
 * needs. The contract asks for a 16 kHz mono 16-bit WAV, so the recorder asks the browser for that
 * rate, follows the rate the context actually gave it (a browser is free to ignore the request) and
 * encodes exactly what the API accepts. Nothing is persisted: the clip is a `Blob` that the caller
 * sends and drops.
 */

/** Contract §5: the backend rejects anything longer than this. */
export const MAX_RECORDING_MS = 120_000;

const TARGET_RATE = 16_000;
const SAMPLE_WIDTH = 2;
/** 16-bit PCM is stored in a signed 16-bit integer, so full scale is one bit less. */
const PCM_SCALE = 0x7fff;

export type RecordingFailure =
  /** The browser has no microphone support at all. */
  | "unsupported"
  /** The user said no, or the browser remembers a previous no. */
  | "denied"
  /** No device, or the device is busy. */
  | "unavailable";

export class RecordingError extends Error {
  readonly kind: RecordingFailure;

  constructor(kind: RecordingFailure, message: string) {
    super(message);
    this.name = "RecordingError";
    this.kind = kind;
  }
}

/** Browser error names that mean "permission", mapped to the UI states of desing.md §8. */
function classify(error: unknown): RecordingFailure {
  const name = error instanceof DOMException ? error.name : "";
  if (name === "NotAllowedError" || name === "SecurityError") return "denied";
  return "unavailable";
}

type AudioContextConstructor = typeof AudioContext;

function audioContextClass(): AudioContextConstructor | null {
  const scope = window as unknown as {
    AudioContext?: AudioContextConstructor;
    webkitAudioContext?: AudioContextConstructor;
  };
  return scope.AudioContext ?? scope.webkitAudioContext ?? null;
}

/**
 * Average the samples into `target` buckets: the browser records at whatever the device gives
 * (usually 48 kHz) and the API only takes 16 kHz. A plain mean is enough for speech and keeps the
 * file small.
 */
function resample(samples: Float32Array, from: number, to: number): Float32Array {
  if (from === to) return samples;
  const ratio = from / to;
  const length = Math.floor(samples.length / ratio);
  const output = new Float32Array(length);
  for (let index = 0; index < length; index += 1) {
    const start = Math.floor(index * ratio);
    const end = Math.min(Math.floor((index + 1) * ratio), samples.length);
    let sum = 0;
    for (let cursor = start; cursor < end; cursor += 1) sum += samples[cursor] ?? 0;
    output[index] = end > start ? sum / (end - start) : 0;
  }
  return output;
}

/** Float samples in [-1, 1] → the 16-bit PCM the WAV header describes. */
function toPcm(samples: Float32Array): ArrayBuffer {
  const buffer = new ArrayBuffer(samples.length * SAMPLE_WIDTH);
  const view = new DataView(buffer);
  samples.forEach((sample, index) => {
    const clamped = Math.max(-1, Math.min(1, sample));
    view.setInt16(index * SAMPLE_WIDTH, Math.round(clamped * PCM_SCALE), true);
  });
  return buffer;
}

/** A mono 16-bit WAV file, header included. */
export function encodeWav(samples: Float32Array, sampleRate: number): Blob {
  const pcm = toPcm(samples);
  const header = new ArrayBuffer(44);
  const view = new DataView(header);
  const write = (offset: number, text: string) => {
    for (let index = 0; index < text.length; index += 1) {
      view.setUint8(offset + index, text.charCodeAt(index));
    }
  };

  write(0, "RIFF");
  view.setUint32(4, 36 + pcm.byteLength, true);
  write(8, "WAVE");
  write(12, "fmt ");
  view.setUint32(16, 16, true); // PCM header size
  view.setUint16(20, 1, true); // PCM, not compressed
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * SAMPLE_WIDTH, true); // byte rate
  view.setUint16(32, SAMPLE_WIDTH, true); // block align
  view.setUint16(34, 16, true); // bits per sample
  write(36, "data");
  view.setUint32(40, pcm.byteLength, true);

  return new Blob([header, pcm], { type: "audio/wav" });
}

/** What the composer needs from a recording: the clip and how it ended. */
export interface Recording {
  blob: Blob;
  durationMs: number;
  /** `true` when the contract limit stopped the recording instead of the user. */
  autoStopped: boolean;
}

/**
 * One recording at a time. `start` asks for the microphone and begins collecting; `stop` closes
 * the graph and resolves the WAV; `cancel` discards everything, so a cancelled recording can never
 * reach the API.
 */
export class VoiceRecorder {
  private stream: MediaStream | null = null;
  private context: AudioContext | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private processor: ScriptProcessorNode | null = null;
  private chunks: Float32Array[] = [];
  private rate = TARGET_RATE;
  private startedAt = 0;
  private cancelled = false;

  get isRecording(): boolean {
    return this.stream !== null;
  }

  /**
   * Ask for the microphone and start collecting. The permission prompt only appears here: never on
   * load (desing.md §8, «Iniciar voz → solicitar permiso cuando corresponda»).
   */
  async start(): Promise<void> {
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new RecordingError("unsupported", "Este navegador no puede grabar audio.");
    }
    const Context = audioContextClass();
    if (!Context) {
      throw new RecordingError("unsupported", "Este navegador no puede procesar audio.");
    }

    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: TARGET_RATE,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
    } catch (error) {
      throw new RecordingError(classify(error), "No pudimos acceder al micrófono.");
    }

    this.cancelled = false;
    this.chunks = [];
    this.startedAt = Date.now();

    this.context = new Context({ sampleRate: TARGET_RATE });
    // Asking for 16 kHz is a hint: the device may give another rate and the clip is resampled later.
    this.rate = Math.round(this.context.sampleRate) || TARGET_RATE;
    this.source = this.context.createMediaStreamSource(this.stream);
    // `ScriptProcessorNode` is deprecated, but the worklet alternative needs a separate module and a
    // build step for one node (stack.md: no new tooling). Speech does not need the extra fidelity.
    this.processor = this.context.createScriptProcessor(4096, 1, 1);
    this.processor.onaudioprocess = (event) => {
      if (this.cancelled) return;
      this.chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
    };
    this.source.connect(this.processor);
    // A script processor only runs while it is connected to a destination; the gain stays at zero.
    const silence = this.context.createGain();
    silence.gain.value = 0;
    this.processor.connect(silence);
    silence.connect(this.context.destination);
  }

  /** Close the graph and return the clip. A cancelled or empty recording resolves `null`. */
  async stop(): Promise<Recording | null> {
    const chunks = this.chunks;
    const cancelled = this.cancelled;
    const durationMs = Date.now() - this.startedAt;
    const rate = this.rate;
    await this.release();

    if (cancelled || chunks.length === 0) return null;

    const samples = resample(concat(chunks), rate, TARGET_RATE);
    return { blob: encodeWav(samples, TARGET_RATE), durationMs, autoStopped: durationMs >= MAX_RECORDING_MS };
  }

  /** Discard the clip: closing the stream stops the browser's recording indicator. */
  async cancel(): Promise<void> {
    this.cancelled = true;
    this.chunks = [];
    await this.release();
  }

  private async release(): Promise<void> {
    if (this.processor) {
      this.processor.onaudioprocess = null;
      this.processor.disconnect();
    }
    this.source?.disconnect();
    this.stream?.getTracks().forEach((track) => track.stop());
    if (this.context) {
      await this.context.close().catch(() => undefined);
    }
    this.processor = null;
    this.source = null;
    this.stream = null;
    this.context = null;
    this.chunks = [];
  }
}

function concat(chunks: Float32Array[]): Float32Array {
  const total = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const output = new Float32Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    output.set(chunk, offset);
    offset += chunk.length;
  }
  return output;
}

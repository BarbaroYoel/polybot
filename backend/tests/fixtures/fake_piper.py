#!/usr/bin/env python3
"""A stand-in for the Piper binary used by the TTS adapter tests (ADR-016).

It speaks the same command line the adapter builds (`--model`, `--output_file`, `--length_scale`,
text on stdin) and writes a real, tiny WAV, so the adapter is tested against real subprocesses and
real files without a model.

Behaviour is driven by `FAKE_PIPER_MODE`:

| Mode   | What it does                                                   |
|--------|----------------------------------------------------------------|
| `ok`   | writes a 22.05 kHz mono 16-bit WAV and exits 0                  |
| `fail` | writes to stderr and exits 2                                   |
| `slow` | sleeps until killed or timed out                               |
"""

from __future__ import annotations

import os
import sys
import time
import wave

MODE = os.environ.get("FAKE_PIPER_MODE", "ok")


def option(name: str) -> str | None:
    argv = sys.argv[1:]
    if name in argv:
        index = argv.index(name)
        return argv[index + 1] if index + 1 < len(argv) else None
    return None


def main() -> None:
    text = sys.stdin.read()
    argv_file = os.environ.get("FAKE_PIPER_ARGV_FILE")
    if argv_file:
        with open(argv_file, "w", encoding="utf-8") as handle:
            handle.write("\n".join(sys.argv[1:]))
    prompt_file = os.environ.get("FAKE_PIPER_TEXT_FILE")
    if prompt_file:
        with open(prompt_file, "w", encoding="utf-8") as handle:
            handle.write(text)

    if MODE == "slow":
        time.sleep(120)

    if MODE == "fail":
        sys.stderr.write("piper: could not load the voice\n")
        sys.exit(2)

    output = option("--output_file")
    if not output:
        sys.stderr.write("piper: --output_file is required\n")
        sys.exit(2)

    # 0.2 s of silence at the sample rate the models use, so the header matches the contract.
    frames = b"\x00\x00" * 4_410
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(22_050)
        wav.writeframes(frames)


if __name__ == "__main__":
    main()

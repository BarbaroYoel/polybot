#!/usr/bin/env python3
"""A stand-in for `opencode run --format json` used by the adapter tests (ADR-019).

It emits the same JSONL events the real CLI produces for text parts, so the adapter is tested
against real pipes, process lifecycle and framing without a model, credentials or the network.

Behavior is driven by `FAKE_OPENCODE_MODE`:

| Mode                | What it emits                                                        |
|---------------------|----------------------------------------------------------------------|
| `ok`                | two text parts, `Bonjour` and ` !`                                  |
| `cumulative`        | the same part resent as `Bonjour` then `Bonjour !`                   |
| `error`             | an `error` record                                                    |
| `garbage`           | a non-JSON line before the normal stream                             |
| `empty`             | no text part at all                                                  |
| `slow`              | one text part, then it sleeps until killed or timed out              |
| `huge`              | a 300k-character text part                                          |
| `feedback-json`     | the closing-turn JSON the adapter parses                             |
| `feedback-broken`   | prose instead of JSON: the closing call must fail, not guess         |
| `translate`         | one translated sentence, from `FAKE_OPENCODE_TRANSLATION`            |
| `translate-quoted`  | the same sentence wrapped in quotes                                  |
| `translate-empty`   | no text: the translation must fail, not return ""                    |
| `lesson`            | a short lesson comment                                              |
| `fail`              | nothing on stdout, an error on stderr and exit 2                    |

The prompt travels as the last argv item (after `--`). Tests read `FAKE_OPENCODE_PROMPT_FILE`,
`FAKE_OPENCODE_ARGV_FILE`, `FAKE_OPENCODE_CWD_FILE` and `FAKE_OPENCODE_PID_FILE`.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

MODE = os.environ.get("FAKE_OPENCODE_MODE", "ok")


def emit(record: dict) -> None:
    sys.stdout.write(json.dumps(record, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def text(value: str, part_id: str = "prt_text_0") -> None:
    emit({"type": "text", "part": {"id": part_id, "type": "text", "text": value}})


def step_start() -> None:
    emit({"type": "step_start"})


def step_finish() -> None:
    emit({"type": "step_finish"})


def run_ok() -> None:
    step_start()
    text("Bonjour", "prt_text_0")
    text(" !", "prt_text_1")
    step_finish()


def run_cumulative() -> None:
    step_start()
    text("Bonjour", "prt_text_0")
    text("Bonjour !", "prt_text_0")
    step_finish()


def run_error() -> None:
    emit(
        {
            "type": "error",
            "error": {
                "type": "provider.invalid-request",
                "message": "provider-side detail that must not reach the user",
            },
        }
    )


def run_garbage() -> None:
    sys.stdout.write("this line is not json\n")
    sys.stdout.flush()
    run_ok()


def run_empty() -> None:
    step_start()
    step_finish()


def run_slow() -> None:
    step_start()
    text("Bon")
    time.sleep(120)


def run_huge() -> None:
    step_start()
    text("x" * 300_000)
    step_finish()


FEEDBACK_PAYLOAD = {
    "corrections": [
        {
            "original": "Je suis allé au café hier",
            "corrected": "Je suis allé au café hier.",
            "explanation": "Falta el punto final.",
        }
    ],
    "vocabulary": [
        {"term": "un café", "translation": "un café", "note": "masculino"},
    ],
}


def run_feedback_json() -> None:
    step_start()
    text(json.dumps(FEEDBACK_PAYLOAD, ensure_ascii=False))
    step_finish()


def run_feedback_broken() -> None:
    step_start()
    text("No pude revisar tu mensaje, probá otra vez en un rato.")
    step_finish()


TRANSLATION = os.environ.get("FAKE_OPENCODE_TRANSLATION", "¿Cómo estás?")


def run_translation(value: str) -> None:
    step_start()
    if value:
        text(value)
    step_finish()


def main() -> None:
    argv = sys.argv[1:]
    prompt = argv[-1] if argv else ""
    prompt_file = os.environ.get("FAKE_OPENCODE_PROMPT_FILE")
    if prompt_file:
        Path(prompt_file).write_text(prompt, encoding="utf-8")
    argv_file = os.environ.get("FAKE_OPENCODE_ARGV_FILE")
    if argv_file:
        Path(argv_file).write_text("\n".join(argv), encoding="utf-8")
    cwd_file = os.environ.get("FAKE_OPENCODE_CWD_FILE")
    if cwd_file:
        Path(cwd_file).write_text(os.getcwd(), encoding="utf-8")
    pid_file = os.environ.get("FAKE_OPENCODE_PID_FILE")
    if pid_file:
        Path(pid_file).write_text(str(os.getpid()), encoding="utf-8")

    if MODE == "ok":
        run_ok()
    elif MODE == "cumulative":
        run_cumulative()
    elif MODE == "error":
        run_error()
    elif MODE == "garbage":
        run_garbage()
    elif MODE == "empty":
        run_empty()
    elif MODE == "slow":
        run_slow()
    elif MODE == "huge":
        run_huge()
    elif MODE == "feedback-json":
        run_feedback_json()
    elif MODE == "feedback-broken":
        run_feedback_broken()
    elif MODE == "translate":
        run_translation(TRANSLATION)
    elif MODE == "translate-quoted":
        run_translation(f'"{TRANSLATION}"')
    elif MODE == "translate-empty":
        run_translation("")
    elif MODE == "lesson":
        run_translation("Muy bien: solo falta el acento de «élève».")
    elif MODE == "fail":
        sys.stderr.write("opencode: no model configured\n")
        sys.exit(2)
    else:
        raise SystemExit(f"unknown FAKE_OPENCODE_MODE: {MODE}")


if __name__ == "__main__":
    main()

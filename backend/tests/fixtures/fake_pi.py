#!/usr/bin/env python3
"""A stand-in for `pi --print --mode json` used by the adapter tests.

It speaks the same JSONL protocol the real CLI documents in `docs/json.md` of the
`pi-coding-agent` package, so the adapter is tested against real pipes, real process
lifecycle and real framing without depending on the network, a model or credentials.

Behavior is driven by `FAKE_PI_MODE`:

| Mode              | What it emits                                                       |
|-------------------|---------------------------------------------------------------------|
| `ok`              | header, user message, two text deltas, authoritative `message_end`   |
| `error`           | a provider `error` update and an assistant `message_end` with error  |
| `garbage`         | a non-JSON line before the normal stream                             |
| `slow`            | one delta, then it sleeps until it is killed or times out            |
| `feedback-json`   | the closing-turn JSON the adapter parses (F3 S7)                     |
| `feedback`        | alias of `feedback-json`, kept for older fixtures                    |
| `feedback-broken` | prose instead of JSON: the closing call must fail, not guess         |
| `translate`       | one translated sentence, from `FAKE_PI_TRANSLATION` (ADR-014)        |
| `translate-quoted`| the same sentence wrapped in double quotes                            |
| `translate-empty` | an empty answer: the translation must fail, not return ""            |

Tests read `FAKE_PI_PROMPT_FILE` (the prompt received on stdin), `FAKE_PI_SYSTEM_FILE` (the
`--system-prompt` value), `FAKE_PI_ARGV_FILE` (the whole argv, so a test can prove the flags that
keep the tutor away from the repository) and `FAKE_PI_PID_FILE` (the child pid, so a test can
prove the process was terminated).
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

MODE = os.environ.get("FAKE_PI_MODE", "ok")


def emit(record: dict) -> None:
    sys.stdout.write(json.dumps(record, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def header() -> None:
    emit(
        {
            "type": "session",
            "version": 3,
            "id": "00000000-0000-4000-8000-000000000000",
            "timestamp": "2026-10-22T14:00:00.000Z",
            "cwd": os.getcwd(),
        }
    )


def user_message(prompt: str) -> None:
    message = {"role": "user", "content": prompt, "timestamp": 1733234401000}
    emit({"type": "agent_start"})
    emit({"type": "turn_start"})
    emit({"type": "message_start", "message": message})
    emit({"type": "message_end", "message": message})


def assistant_start() -> None:
    emit(
        {
            "type": "message_start",
            "message": {
                "role": "assistant",
                "content": [],
                "stopReason": "pending",
                "timestamp": 1733234402000,
            },
        }
    )


def delta(text: str, index: int = 0) -> None:
    emit(
        {
            "type": "message_update",
            "usage": {"input": 10, "output": 2, "totalTokens": 12},
            "assistantMessageEvent": {
                "type": "text_delta",
                "contentIndex": index,
                "delta": text,
            },
        }
    )


def assistant_end(content: str, stop_reason: str = "stop") -> None:
    message = {
        "role": "assistant",
        "content": [{"type": "text", "text": content}],
        "stopReason": stop_reason,
        "timestamp": 1733234403000,
    }
    emit({"type": "message_end", "message": message})
    emit({"type": "turn_end", "message": message, "toolResults": []})
    emit({"type": "agent_end", "messages": [message], "willRetry": False})
    emit({"type": "agent_settled", "aborted": stop_reason == "aborted"})


def run_ok(prompt: str) -> None:
    header()
    user_message(prompt)
    assistant_start()
    # A thinking block and a tool-call block must be ignored by the adapter.
    emit(
        {
            "type": "message_update",
            "assistantMessageEvent": {"type": "thinking_start", "contentIndex": 0},
        }
    )
    emit(
        {
            "type": "message_update",
            "assistantMessageEvent": {
                "type": "thinking_delta",
                "contentIndex": 0,
                "delta": "debo saludar",
            },
        }
    )
    delta("Bonjour", 1)
    delta(" !", 1)
    emit(
        {
            "type": "message_update",
            "assistantMessageEvent": {
                "type": "text_end",
                "contentIndex": 1,
                "content": "Bonjour !",
            },
        }
    )
    assistant_end("Bonjour !")


def run_error() -> None:
    header()
    user_message("hola")
    assistant_start()
    emit(
        {
            "type": "message_update",
            "assistantMessageEvent": {
                "type": "error",
                "reason": "error",
                "error": "provider overloaded",
            },
        }
    )
    assistant_end("", stop_reason="error")


def run_garbage() -> None:
    header()
    user_message("hola")
    sys.stdout.write("this line is not json\n")
    sys.stdout.flush()
    assistant_start()
    delta("ok")
    assistant_end("ok")


def run_huge() -> None:
    header()
    user_message("hola")
    assistant_start()
    delta("x" * 300_000)
    assistant_end("x" * 300_000)


def run_no_stdin() -> None:
    # A child that never reads its stdin: a prompt larger than the pipe buffer blocks `drain()`.
    header()
    time.sleep(120)


def run_slow() -> None:
    header()
    user_message("hola")
    assistant_start()
    delta("Bon")
    time.sleep(120)


FEEDBACK_PAYLOAD = {
    "corrections": [
        {
            "original": "Je suis allé au café hier",
            "corrected": "Je suis allé au café hier.",
            "explanation": "Falta el punto final.",
        },
        {
            "original": "j'ai prends un café",
            "corrected": "je prends un café",
            "explanation": "«prendre» va en presente sin auxiliar.",
        },
    ],
    "vocabulary": [
        {"term": "un café", "translation": "un café", "note": "masculino"},
        {"term": "s'il vous plaît", "translation": "por favor", "note": None},
    ],
}


def run_feedback_json() -> None:
    header()
    user_message("hola")
    assistant_start()
    text = json.dumps(FEEDBACK_PAYLOAD, ensure_ascii=False)
    delta(text)
    assistant_end(text)


def run_feedback_broken() -> None:
    """The model answers with prose: the adapter cannot parse it and must fail."""
    header()
    user_message("hola")
    assistant_start()
    text = "No pude revisar tu mensaje, probá otra vez en un rato."
    delta(text)
    assistant_end(text)


def run_empty() -> None:
    header()
    user_message("hola")
    assistant_start()
    assistant_end("")


TRANSLATION = os.environ.get("FAKE_PI_TRANSLATION", "¿Cómo estás?")


def run_translation(text: str) -> None:
    header()
    user_message("traducir")
    assistant_start()
    if text:
        delta(text)
    assistant_end(text)


def main() -> None:
    prompt = sys.stdin.read()
    prompt_file = os.environ.get("FAKE_PI_PROMPT_FILE")
    if prompt_file:
        Path(prompt_file).write_text(prompt, encoding="utf-8")
    pid_file = os.environ.get("FAKE_PI_PID_FILE")
    if pid_file:
        Path(pid_file).write_text(str(os.getpid()), encoding="utf-8")
    argv_file = os.environ.get("FAKE_PI_ARGV_FILE")
    if argv_file:
        Path(argv_file).write_text("\n".join(sys.argv[1:]), encoding="utf-8")
    system_file = os.environ.get("FAKE_PI_SYSTEM_FILE")
    if system_file and "--system-prompt" in sys.argv[1:]:
        index = sys.argv[1:].index("--system-prompt")
        Path(system_file).write_text(sys.argv[index + 2], encoding="utf-8")

    if MODE == "ok":
        run_ok(prompt)
    elif MODE == "error":
        run_error()
    elif MODE == "garbage":
        run_garbage()
    elif MODE == "slow":
        run_slow()
    elif MODE == "huge":
        run_huge()
    elif MODE == "no-stdin":
        run_no_stdin()
    elif MODE in {"feedback", "feedback-json"}:
        run_feedback_json()
    elif MODE == "feedback-broken":
        run_feedback_broken()
    elif MODE == "empty":
        run_empty()
    elif MODE == "translate":
        run_translation(TRANSLATION)
    elif MODE == "translate-quoted":
        run_translation(f'"{TRANSLATION}"')
    elif MODE == "translate-empty":
        run_translation("")
    elif MODE == "fail":
        sys.stderr.write("pi: no credentials configured\n")
        sys.exit(2)
    else:
        raise SystemExit(f"unknown FAKE_PI_MODE: {MODE}")


if __name__ == "__main__":
    main()

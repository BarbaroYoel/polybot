"""Tutor prompt, versioned in the repository (F3 S3).

Two files carry the prompt: the system prompt with the tutor rules and the turn template that
frames the history and the new message. `PROMPT_VERSION` is asserted by the tests so a change in
behavior is visible in the diff.
"""

from dataclasses import dataclass
from pathlib import Path
from string import Template

from app.ports.llm import TutorContext, TutorTurn

PROMPT_VERSION = "tutor.v1"

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
_NO_HISTORY = "(todavía no hay mensajes)"


@dataclass(frozen=True, slots=True)
class TutorPrompt:
    """The versioned prompt files, ready to render for one turn."""

    system: str
    turn: str

    @classmethod
    def load(cls, version: str = PROMPT_VERSION) -> "TutorPrompt":
        if not version.startswith("tutor."):
            raise ValueError(f"unexpected prompt version: {version}")
        suffix = version.removeprefix("tutor.")
        return cls(
            system=(_PROMPTS_DIR / f"tutor.{suffix}.md").read_text(encoding="utf-8"),
            turn=(_PROMPTS_DIR / f"turn.{suffix}.txt").read_text(encoding="utf-8"),
        )

    def render_system(self, context: TutorContext) -> str:
        return Template(self.system).substitute(
            language_name=context.language_name,
            language_code=context.language_code,
            level=context.level.value,
            explanation_language=context.explanation_language,
        )

    def render_turn(self, turn: TutorTurn) -> str:
        history = (
            "\n".join(
                f"{'Estudiante' if message.author.value == 'user' else 'Tutor'}: {message.content}"
                for message in turn.history
            )
            or _NO_HISTORY
        )
        return Template(self.turn).substitute(
            history=history,
            user_message=turn.user_message,
        )

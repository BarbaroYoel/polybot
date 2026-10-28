"""The example catalog as data (ADR-021).

The `choice` type is only deterministic while the content is consistent: the comparison grades the
option the student picked against the accepted answers, so a correct option that is not in
`answers` could never be right, and an option duplicated by mistake would offer the same answer
twice. These are content rules, not rendering rules, so they are tested here without a database.
"""

from app.adapters.db.lesson_content import CATALOG, TERMS

# A choice with a single option is not a choice, and a long list stops being readable on a phone.
MIN_OPTIONS = 2
MAX_OPTIONS = 6


def _exercises() -> list[tuple[str, str, object]]:
    return [
        (code, lesson.title, exercise)
        for code, units in CATALOG.items()
        for unit in units
        for lesson in unit.lessons
        for exercise in lesson.exercises
    ]


def test_every_language_offers_at_least_one_choice() -> None:
    for code in CATALOG:
        kinds = {
            exercise.kind
            for unit in CATALOG[code]
            for lesson in unit.lessons
            for exercise in lesson.exercises
        }
        # Both types coexist in the catalog: a language with only one of them would leave half the
        # renderer untested by the seed.
        assert kinds == {"writing", "choice"}, code


def test_a_choice_offers_readable_unique_options() -> None:
    for code, title, exercise in _exercises():
        if exercise.kind != "choice":
            continue
        where = f"{code} · {title}"
        assert MIN_OPTIONS <= len(exercise.options) <= MAX_OPTIONS, where
        assert len(set(exercise.options)) == len(exercise.options), f"duplicate option in {where}"
        assert all(option.strip() for option in exercise.options), where


def test_a_choice_accepts_exactly_the_right_option() -> None:
    for code, title, exercise in _exercises():
        if exercise.kind != "choice":
            continue
        where = f"{code} · {title}"
        # One accepted answer, and it is one of the options: anything else makes the exercise
        # impossible to solve or reveals more than one right option.
        assert len(exercise.answers) == 1, where
        assert exercise.answers[0] in exercise.options, where
        assert exercise.explanation.strip(), where


def test_a_written_exercise_offers_no_options() -> None:
    for code, title, exercise in _exercises():
        if exercise.kind != "writing":
            continue
        assert exercise.options == (), f"{code} · {title}"
        assert exercise.answers, f"{code} · {title}"


def test_every_lesson_title_is_unique_because_terms_are_keyed_by_title() -> None:
    titles = [
        lesson.title for units in CATALOG.values() for unit in units for lesson in unit.lessons
    ]

    assert len(titles) == len(set(titles))
    assert set(titles) == set(TERMS)

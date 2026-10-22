"""Language use cases (docs/api-contract.md §3 "Idiomas")."""

from app.domain.entities import CefrLevel, LanguageProfile, NewLanguage, WeeklyGoal
from app.domain.errors import (
    ActiveLanguageCannotBeArchived,
    LanguageAlreadyExists,
    LanguageNotFound,
    LastLanguageCannotBeArchived,
)
from app.ports.repositories import LanguageRepository


class LanguageService:
    def __init__(self, languages: LanguageRepository) -> None:
        self._languages = languages

    async def list_languages(self) -> list[LanguageProfile]:
        return await self._languages.list_languages()

    async def add_language(
        self,
        *,
        code: str,
        name: str,
        level: CefrLevel,
        explanation_language: str,
        weekly_goal: WeeklyGoal,
    ) -> LanguageProfile:
        normalized_code = code.strip().lower()
        if await self._languages.get_language_by_code(normalized_code) is not None:
            raise LanguageAlreadyExists(normalized_code)

        return await self._languages.add_language(
            NewLanguage(
                code=normalized_code,
                name=name.strip(),
                level=level,
                explanation_language=explanation_language.strip().lower(),
                weekly_goal=weekly_goal,
            )
        )

    async def update_language(
        self,
        language_id: str,
        *,
        level: CefrLevel | None = None,
        weekly_goal: WeeklyGoal | None = None,
        is_active: bool | None = None,
    ) -> LanguageProfile:
        if await self._languages.get_language(language_id) is None:
            raise LanguageNotFound(language_id)
        return await self._languages.update_language(
            language_id, level=level, weekly_goal=weekly_goal, is_active=is_active
        )

    async def archive_language(self, language_id: str) -> None:
        existing = await self._languages.get_language(language_id)
        if existing is None:
            raise LanguageNotFound(language_id)
        if existing.is_active:
            # Silently switching the user's context would be worse than an actionable error.
            raise ActiveLanguageCannotBeArchived(language_id)

        remaining = [row for row in await self._languages.list_languages() if row.id != language_id]
        if not remaining:
            raise LastLanguageCannotBeArchived(language_id)

        await self._languages.archive_language(language_id)

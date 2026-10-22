import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { ApiError } from "./api/client";
import { listLanguages, updateLanguage } from "./api/languages";
import type { LanguageProfile } from "./api/types";
import type { AsyncStatus } from "./useAsync";
import { useAsync } from "./useAsync";

const STORAGE_KEY = "polybot.activeLanguage";

interface LanguageContextValue {
  status: AsyncStatus;
  languages: LanguageProfile[];
  /** The language with `is_active` on the server; `null` while loading, on error or when none is set. */
  active: LanguageProfile | null;
  error: ApiError | null;
  /** Activates `code` on the server (`PATCH is_active`). Rejects with an `ApiError` the caller shows. */
  setActiveCode: (code: string) => Promise<void>;
  reload: () => void;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

/**
 * Non-authoritative hint of the last language this browser saw active. It is never read to decide
 * the active language — the server's `is_active` is the only source of truth (F2 S9) — it only
 * keeps the value around so a later offline shell can remember the last context.
 */
function rememberCode(code: string): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, code);
  } catch {
    // No storage available: the active language lives in server state only.
  }
}

/**
 * Single active language (desing.md §4, AGENTS.md §3). The list comes from `GET /languages`, so
 * changing `is_active` anywhere else is reflected on the next reload instead of being guessed.
 */
export function LanguageProvider({ children }: { children: ReactNode }) {
  const { status, data, error, reload } = useAsync(listLanguages, []);
  const [languages, setLanguages] = useState<LanguageProfile[]>([]);

  // The hook clears its data when a new load starts. The provider keeps the last known list so the
  // shell does not blink on a reload; the server response always replaces it when it arrives.
  useEffect(() => {
    if (data) setLanguages(data);
  }, [data]);

  const active = useMemo(
    () => languages.find((language) => language.is_active) ?? null,
    [languages],
  );

  useEffect(() => {
    if (active) rememberCode(active.code);
  }, [active]);

  const setActiveCode = useCallback(
    async (code: string) => {
      const target = languages.find((language) => language.code === code);
      // Activating the active language (or an unknown code) changes nothing on the server.
      if (!target || target.is_active) return;

      const updated = await updateLanguage(target.id, { is_active: true });
      // Activating one language deactivates the previous one (docs/api-contract.md §3): mirror the
      // response so the UI and the server agree without a second round trip.
      setLanguages((current) =>
        current.map((language) => {
          if (language.id === updated.id) return updated;
          return language.is_active ? { ...language, is_active: false } : language;
        }),
      );
    },
    [languages],
  );

  const value = useMemo<LanguageContextValue>(
    () => ({ status, languages, active, error, setActiveCode, reload }),
    [status, languages, active, error, setActiveCode, reload],
  );

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useActiveLanguage(): LanguageContextValue {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error("useActiveLanguage must be used inside LanguageProvider");
  }
  return context;
}

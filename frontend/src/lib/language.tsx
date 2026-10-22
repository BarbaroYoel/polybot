import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { LANGUAGES } from "./fixtures";
import type { LanguageProfile } from "./types";

const STORAGE_KEY = "polybot.activeLanguage";

interface LanguageContextValue {
  languages: LanguageProfile[];
  active: LanguageProfile;
  setActiveCode: (code: string) => void;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

function readStoredCode(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

/**
 * Idioma activo único (desing.md §4). Persiste entre recargas para que la app
 * retome el idioma en el que estaba el usuario.
 */
export function LanguageProvider({ children }: { children: ReactNode }) {
  const [activeCode, setActiveCodeState] = useState<string>(() => {
    const stored = readStoredCode();
    const match = LANGUAGES.find((language) => language.code === stored);
    return match?.code ?? LANGUAGES[0]?.code ?? "en";
  });

  const setActiveCode = useCallback((code: string) => {
    setActiveCodeState(code);
    try {
      window.localStorage.setItem(STORAGE_KEY, code);
    } catch {
      // Sin almacenamiento disponible: el idioma activo vive solo en memoria.
    }
  }, []);

  const value = useMemo<LanguageContextValue>(() => {
    const fallback: LanguageProfile = { code: "en", name: "Inglés", level: "A1", conversationCount: 0 };
    const active = LANGUAGES.find((language) => language.code === activeCode) ?? fallback;
    return { languages: LANGUAGES, active, setActiveCode };
  }, [activeCode, setActiveCode]);

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useActiveLanguage(): LanguageContextValue {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error("useActiveLanguage must be used inside LanguageProvider");
  }
  return context;
}

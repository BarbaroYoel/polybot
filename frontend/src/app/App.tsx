import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/States";
import { LanguageProvider } from "../lib/language";
import {
  LanguagesPage,
  LessonsPage,
  NotFoundPage,
  PlansPage,
  ProgressPage,
  SettingsPage,
  TranslatePage,
} from "../features/sections/pages";

export function App() {
  return (
    <LanguageProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route
              index
              element={
                <EmptyState
                  title="Carcasa lista"
                  description="La navegación y los idiomas ya funcionan. La pantalla de conversación llega en el próximo commit."
                />
              }
            />
            <Route path="chat" element={<Navigate to="/" replace />} />
            <Route path="lessons" element={<LessonsPage />} />
            <Route path="plans" element={<PlansPage />} />
            <Route path="translate" element={<TranslatePage />} />
            <Route path="progress" element={<ProgressPage />} />
            <Route path="languages" element={<LanguagesPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </LanguageProvider>
  );
}

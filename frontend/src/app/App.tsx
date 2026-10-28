import { Component, Suspense, lazy } from "react";
import type { ErrorInfo, ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { ErrorState, LoadingState } from "../components/States";
import { LanguageProvider } from "../lib/language";
import {
  NotFoundPage,
  SettingsPage,
  TranslatePage,
} from "../features/sections/pages";
import { HomePage } from "../features/home/HomePage";
import { LanguagesPage } from "../features/languages/LanguagesPage";
import { LessonPage } from "../features/lessons/LessonPage";
import { LessonsPage } from "../features/lessons/LessonsPage";
import { PlansPage } from "../features/plans/PlansPage";
import { ProgressPage } from "../features/progress/ProgressPage";

const ChatPage = lazy(async () => {
  const module = await import("../features/chat/ChatPage");
  return { default: module.ChatPage };
});

interface BoundaryProps {
  children: ReactNode;
}

interface BoundaryState {
  error: Error | null;
}

class RouteErrorBoundary extends Component<BoundaryProps, BoundaryState> {
  state: BoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): BoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("Route error", error, info.componentStack);
  }

  render(): ReactNode {
    const { error } = this.state;
    if (error) {
      return (
        <ErrorState
          title="Algo se rompió en esta pantalla"
          description={error.message}
          action={
            <button type="button" className="chips__item" onClick={() => this.setState({ error: null })}>
              Reintentar
            </button>
          }
        />
      );
    }
    return this.props.children;
  }
}

export function App() {
  return (
    <LanguageProvider>
      <BrowserRouter>
        <RouteErrorBoundary>
          <Routes>
            <Route element={<AppShell />}>
              <Route index element={<HomePage />} />
              <Route path="chat" element={<Navigate to="/" replace />} />
              <Route
                path="chat/:conversationId"
                element={
                  <Suspense fallback={<LoadingState label="Cargando conversación…" />}>
                    <ChatPage />
                  </Suspense>
                }
              />
              <Route path="lessons" element={<LessonsPage />} />
              <Route path="lessons/:lessonId" element={<LessonPage />} />
              <Route path="plans" element={<PlansPage />} />
              <Route path="translate" element={<TranslatePage />} />
              <Route path="progress" element={<ProgressPage />} />
              <Route path="languages" element={<LanguagesPage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Routes>
        </RouteErrorBoundary>
      </BrowserRouter>
    </LanguageProvider>
  );
}

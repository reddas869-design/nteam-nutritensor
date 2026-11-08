import {
  Component,
  lazy,
  Suspense,
  useState,
  type ErrorInfo,
  type ReactNode,
} from "react";
import { ArrowUpRight, Menu, X } from "lucide-react";
import { WorkspaceProvider, useWorkspace } from "./state/workspace";
import { Brand } from "./components/Brand";
import { Navigation } from "./components/Navigation";
import { Button, IconButton, Loading } from "./components/Primitives";

const ManualPage = lazy(() => import("./pages/ManualPage"));
const CapturePage = lazy(() => import("./pages/CapturePage"));
const JournalPage = lazy(() => import("./pages/JournalPage"));
const InsightsPage = lazy(() => import("./pages/InsightsPage"));
const RecipesPage = lazy(() => import("./pages/RecipesPage"));
const CatalogPage = lazy(() => import("./pages/CatalogPage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));
const AboutPage = lazy(() => import("./pages/AboutPage"));

class ErrorBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(_error: Error, _info: ErrorInfo) {
    // No remote telemetry: meal content and model output stay out of error reports.
  }
  render() {
    if (this.state.failed)
      return (
        <div className="fatal-error">
          <Brand />
          <h1>sir, plz reload the workspace</h1>
          <p>
            The interface encountered an unexpected error. saved meals
            remain in the workspace.
          </p>
          <Button onClick={() => window.location.reload()}>
            Reload workspace
          </Button>
        </div>
      );
    return this.props.children;
  }
}

function Shell() {
  const { page, setPage, api, connected, toasts, dismissToast, preferences } =
    useWorkspace();
  const [navigation, setNavigation] = useState(false);
  const capturing = page === "capture";
  return (
    <div
      className={`app-shell ${capturing ? "shell-capture" : "shell-workspace"} ${preferences.reduced_motion ? "reduce-motion" : ""}`}
    >
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <header className="app-header">
        <div className="header-left">
          <IconButton
            label="Open menu"
            onClick={() => setNavigation(true)}
            aria-expanded={navigation}
          >
            <Menu size={21} strokeWidth={1.5} />
          </IconButton>
          {!capturing && (
            <button
              className="brand-button"
              onClick={() => setPage("capture")}
              aria-label="NutriTensor home"
            >
              <Brand />
            </button>
          )}
        </div>
        {!capturing && (
          <div className="header-right">
            <button
              className={`workspace-badge ${connected ? "is-connected" : ""}`}
              onClick={() => setPage("settings")}
            >
              <span className="status-dot" />
              <ArrowUpRight size={13} />
            </button>
            <span className="header-index">N° 01</span>
          </div>
        )}
      </header>
      <div id="main-content" tabIndex={-1}>
        <Suspense
          fallback={
            <div className="route-loading">
              <Loading />
            </div>
          }
        >
          {page === "capture" && <CapturePage />}
          {page === "manual" && <ManualPage />}
          {page === "journal" && <JournalPage />}
          {page === "insights" && <InsightsPage />}
          {page === "recipes" && <RecipesPage />}
          {page === "catalog" && <CatalogPage />}
          {page === "settings" && <SettingsPage />}
          {page === "about" && <AboutPage />}
        </Suspense>
      </div>
      <Navigation open={navigation} onClose={() => setNavigation(false)} />
      <div className="toast-stack" aria-live="polite">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`toast toast-${toast.tone}`}
            role={toast.tone === "error" ? "alert" : "status"}
          >
            <span>{toast.message}</span>
            <button
              aria-label="Dismiss notification"
              onClick={() => dismissToast(toast.id)}
            >
              <X size={15} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <WorkspaceProvider>
        <Shell />
      </WorkspaceProvider>
    </ErrorBoundary>
  );
}

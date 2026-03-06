import { useEffect, useState, useCallback } from "react";
import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import CAsPage from "./pages/CAsPage";
import CertificatesPage from "./pages/CertificatesPage";
import CSRsPage from "./pages/CSRsPage";
import SettingsPage from "./pages/SettingsPage";
import Toast from "./components/ui/Toast";
import { useAppStore } from "./store/appStore";

const queryClient = new QueryClient();

interface ToastState {
  message: string;
  type: "success" | "error";
}

function AppShell() {
  const [toast, setToast] = useState<ToastState | null>(null);
  const { theme, toggleTheme } = useAppStore();

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  const showSuccess = useCallback(
    (msg: string) => setToast({ message: msg, type: "success" }),
    []
  );
  const showError = useCallback(
    (msg: string) => setToast({ message: msg, type: "error" }),
    []
  );

  return (
    <>
      <nav className="navbar">
        <span className="navbar-brand">CA Manager</span>
        <div className="navbar-links">
          <NavLink to="/" end>Certificates</NavLink>
          <NavLink to="/cas">CAs</NavLink>
          <NavLink to="/csrs">CSRs</NavLink>
          <NavLink to="/settings">Settings</NavLink>
        </div>
        <button
          className="btn btn-secondary btn-sm"
          onClick={toggleTheme}
          title="Toggle theme"
          style={{ marginLeft: "auto" }}
        >
          {theme === "dark" ? "☀" : "☾"}
        </button>
      </nav>

      <main className="main-content">
        <Routes>
          <Route
            path="/"
            element={
              <CertificatesPage onSuccess={showSuccess} onError={showError} />
            }
          />
          <Route
            path="/cas"
            element={<CAsPage onSuccess={showSuccess} onError={showError} />}
          />
          <Route
            path="/csrs"
            element={<CSRsPage onSuccess={showSuccess} onError={showError} />}
          />
          <Route
            path="/settings"
            element={<SettingsPage onSuccess={showSuccess} onError={showError} />}
          />
        </Routes>
      </main>

      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onDone={() => setToast(null)}
        />
      )}
    </>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppShell />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

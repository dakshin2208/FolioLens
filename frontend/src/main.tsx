import "./index.css";

import { StrictMode, useEffect, useState, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from "react-router-dom";

import { ErrorBoundary } from "./components/ErrorBoundary";
import { AppShell } from "./components/Layout";
import { ToastProvider } from "./components/ui";
import { auth } from "./lib/api";
import { applyTheme, getTheme } from "./lib/theme";
import { AuthPage } from "./pages/AuthPage";
import { ClientReportPage, DemoClientReportPage } from "./pages/ClientReportPage";
import { DemoPage } from "./pages/DemoPage";
import { Landing } from "./pages/Landing";
import { MethodologyPage, NotFoundPage } from "./pages/MethodologyPage";
import { PortfolioPage } from "./pages/PortfolioPage";
import { PortfoliosPage } from "./pages/PortfoliosPage";

function RequireAuth({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const [signedIn, setSignedIn] = useState(Boolean(auth.token));
  useEffect(() => {
    const onLogout = () => {
      setSignedIn(false);
      navigate("/login");
    };
    window.addEventListener("foliolens:logout", onLogout);
    return () => window.removeEventListener("foliolens:logout", onLogout);
  }, [navigate]);
  return signedIn ? <>{children}</> : <Navigate to="/login" replace />;
}

function GuestOnly({ children }: { children: ReactNode }) {
  return auth.token ? <Navigate to="/app" replace /> : <>{children}</>;
}

applyTheme(getTheme());

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
    <BrowserRouter>
      <ToastProvider>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<GuestOnly><AuthPage mode="login" /></GuestOnly>} />
          <Route path="/register" element={<GuestOnly><AuthPage mode="register" /></GuestOnly>} />
          <Route path="/demo" element={<AppShell><DemoPage /></AppShell>} />
          <Route path="/demo/share" element={<DemoClientReportPage />} />
          <Route path="/methodology" element={<AppShell><MethodologyPage /></AppShell>} />
          <Route path="/app" element={<RequireAuth><AppShell><PortfoliosPage /></AppShell></RequireAuth>} />
          <Route path="/app/p/:id" element={<RequireAuth><AppShell><PortfolioPage /></AppShell></RequireAuth>} />
          <Route path="/app/p/:id/share" element={<RequireAuth><ClientReportPage /></RequireAuth>} />
          <Route path="*" element={<AppShell><NotFoundPage /></AppShell>} />
        </Routes>
      </ToastProvider>
    </BrowserRouter>
    </ErrorBoundary>
  </StrictMode>,
);

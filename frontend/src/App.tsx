/**
 * App.tsx - Main application with React Router
 */

import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { getSessionIdFromStorage } from "@/utils/storage";
import Home from "@/pages/Home";
import Explorer from "@/pages/Explorer";

// Protected Route Component
function ProtectedRoute({
  children,
  requiresRepo = false,
}: {
  children: React.ReactNode;
  requiresRepo?: boolean;
}) {
  const sessionId = getSessionIdFromStorage();

  // Check sessionId
  if (!sessionId) {
    return <Navigate to="/" replace />;
  }

  // Check repoId if required (from URL params or localStorage)
  if (requiresRepo) {
    // TODO: Check if repoId exists (we'll add this logic later)
    const repoId = localStorage.getItem("current_repo_id");
    if (!repoId) {
      return <Navigate to="/" replace />;
    }
  }

  return <>{children}</>;
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Home Page - Public */}
        <Route path="/" element={<Home />} />

        {/* Explorer Page - Protected (requires session + repo) */}
        <Route
          path="/explorer/:repoId"
          element={
            <ProtectedRoute requiresRepo={true}>
              <Explorer />
            </ProtectedRoute>
          }
        />

        {/* 404 - Redirect to home */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;

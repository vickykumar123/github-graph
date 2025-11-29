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
}: {
  children: React.ReactNode;
}) {
  const sessionId = getSessionIdFromStorage();

  // Check sessionId - redirect to home if not found
  if (!sessionId) {
    return <Navigate to="/" replace />;
  }

  // repoId comes from URL params, no need to check localStorage
  return <>{children}</>;
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Home Page - Public */}
        <Route path="/" element={<Home />} />

        {/* Explorer Page - Protected (requires session, repoId from URL) */}
        <Route
          path="/explorer/:repoId"
          element={
            <ProtectedRoute>
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

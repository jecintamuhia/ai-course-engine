import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useLocation,
} from "react-router-dom";
import type { ReactNode } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { isAuthenticated } from "@/lib/auth";

import { DashboardPage } from "@/pages/Dashboard";
import { UploadPage } from "@/pages/Upload";
import { DocumentsPage } from "@/pages/Documents";
import { DocumentDetailPage } from "@/pages/DocumentDetail";
import { CurriculumStudioPage } from "@/pages/CurriculumStudio";
import { LessonReviewPage } from "@/pages/LessonReview";
import { LoginPage } from "@/pages/Login";
import { RegisterPage } from "@/pages/Register";
import { PublishPage } from "@/pages/Publish";
import { CoursesPage } from "@/pages/Courses";
import { SystemStatusPage } from "@/pages/SystemStatus";

function RequireAuth({ children }: { children: ReactNode }) {
  const location = useLocation();
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return children;
}

export default function App() {
  return (
    <TooltipProvider delayDuration={200}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route
            element={
              <RequireAuth>
                <AppShell />
              </RequireAuth>
            }
          >
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/documents" element={<DocumentsPage />} />
            <Route path="/document/:id" element={<DocumentDetailPage />} />
            <Route path="/curriculum/:id" element={<CurriculumStudioPage />} />
            <Route
              path="/curriculum/:curriculumId/content/:unitId"
              element={<LessonReviewPage />}
            />
            <Route path="/publish/:id" element={<PublishPage />} />
            <Route path="/courses" element={<CoursesPage />} />
            <Route path="/status" element={<SystemStatusPage />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Route>
        </Routes>
        <Toaster position="top-right" richColors />
      </BrowserRouter>
    </TooltipProvider>
  );
}
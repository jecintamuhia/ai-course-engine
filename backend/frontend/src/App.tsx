import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useLocation,
} from "react-router-dom";
import type { ReactNode } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { LearnerShell } from "@/components/layout/LearnerShell";
import { ErrorBoundary } from "@/components/shared/ErrorBoundary";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { isAuthenticated, isStaff } from "@/lib/auth";
import { DashboardPage } from "@/pages/Dashboard";
import { UploadPage } from "@/pages/Upload";
import { DocumentsPage } from "@/pages/Documents";
import { DocumentDetailPage } from "@/pages/DocumentDetail";
import { CurriculumStudioPage } from "@/pages/CurriculumStudio";
import { LessonReviewPage } from "@/pages/LessonReview";
import { LearnPage } from "@/pages/Learn";
import { LearnerCoursePage } from "@/pages/LearnerCourse";
import { LearnerLessonPage } from "@/pages/LearnerLesson";
import {
  CertificateVerifyPage,
  LearnerAssessmentPage,
} from "@/pages/LearnerAssessment";
import { LearnerReviewsPage } from "@/pages/LearnerReviews";
import { LecturerCoursePage } from "@/pages/LecturerCourse";
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
  // Only authoring roles may render the workspace. A learner that
  // navigates here is sent back to the portal with their session intact
  // — the backend rejects the request with 403 regardless, so the
  // client-side check is convenience, not security.
  if (!isStaff()) {
    return <Navigate to="/learn" replace />;
  }
  return children;
}

function RequireLearner({ children }: { children: ReactNode }) {
  const location = useLocation();
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  // Any signed-in account may open the learner portal. Every endpoint
  // behind it returns only the caller's own records, so a lecturer can
  // preview exactly what a learner sees.
  return children;
}

/** Send a signed-in account to the surface that matches its role. */
function RoleHome() {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }
  return <Navigate to={isStaff() ? "/dashboard" : "/learn"} replace />;
}

export default function App() {
  return (
    <TooltipProvider delayDuration={200}>
      <BrowserRouter>
        <ErrorBoundary>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/verify/:reference" element={<CertificateVerifyPage />} />
            <Route
              element={
                <RequireLearner>
                  <LearnerShell />
                </RequireLearner>
              }
            >
              <Route path="/learn" element={<LearnPage />} />
              <Route path="/learn/course/:courseId" element={<LearnerCoursePage />} />
              <Route
                path="/learn/course/:courseId/lesson/:lessonId"
                element={<LearnerLessonPage />}
              />
              <Route
                path="/learn/course/:courseId/assessment"
                element={<LearnerAssessmentPage />}
              />
            </Route>
            <Route path="/" element={<RoleHome />} />
            <Route
              element={
                <RequireAuth>
                  <AppShell />
                </RequireAuth>
              }
            >
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
              <Route path="/reviews" element={<LearnerReviewsPage />} />
              <Route path="/status" element={<SystemStatusPage />} />
              <Route path="/lecturer/courses/:courseId" element={<LecturerCoursePage />} />
              <Route
                path="/lecturer/courses/:courseId/lessons/:lessonId"
                element={<LecturerCoursePage />}
              />
            </Route>
            <Route path="*" element={<RoleHome />} />
          </Routes>
        </ErrorBoundary>
        <Toaster position="top-right" richColors />
      </BrowserRouter>
    </TooltipProvider>
  );
}

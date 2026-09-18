import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";

import { DashboardPage } from "@/pages/Dashboard";
import { UploadPage } from "@/pages/Upload";
import { DocumentsPage } from "@/pages/Documents";
import { DocumentDetailPage } from "@/pages/DocumentDetail";
import { CurriculumStudioPage } from "@/pages/CurriculumStudio";
import { PublishPage } from "@/pages/Publish";
import { CoursesPage } from "@/pages/Courses";
import { SystemStatusPage } from "@/pages/SystemStatus";

export default function App() {
  return (
    <TooltipProvider delayDuration={200}>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/documents" element={<DocumentsPage />} />
            <Route path="/document/:id" element={<DocumentDetailPage />} />
            <Route path="/curriculum/:id" element={<CurriculumStudioPage />} />
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
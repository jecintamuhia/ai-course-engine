import type {
  AssessmentGenerateRequest,
  AssessmentListResponse,
  AssessmentRead,
  AssessmentReviewRequest,
  AuthMethods,
  BlockReviewRequest,
  CanonicalizationResponse,
  ChunkingResponse,
  ContentGenerationCreateResponse,
  ContentGenerationJob,
  CoverageReportRead,
  CurriculumDetailRead,
  CurriculumGenerateRequest,
  CurriculumGenerateResponse,
  CurriculumListResponse,
  CurriculumReviewRequest,
  DashboardResponse,
  DependencyGraphResponse,
  DocumentOverview,
  DocumentOverviewListResponse,
  DocumentStructureResponse,
  DocumentUploadResponse,
  GenerateWeekResponse,
  IngestionJobCreateResponse,
  IngestionJobRead,
  LessonBlockRead,
  LessonListResponse,
  LessonRead,
  LessonReviewRequest,
  LessonSourceMapRead,
  MoodleConnectionCheck,
  MoodleConnectionStatus,
  MoodleCourseListResponse,
  MoodlePreflightResponse,
  MoodlePublishRequest,
  MoodlePublishResponse,
  MoodleReadyExport,
  MoodleVerifyResponse,
  PageExtractionResponse,
  QAReportRead,
  QAReportResponse,
  RegisterRequest,
  TopicAnalysisResponse,
  TopicProvenanceResponse,
  TopicRead,
  TokenResponse,
  UserRead,
  UUID,
} from "@/lib/types";

import { clearToken, getToken } from "@/lib/auth";

const API_ROOT = "/api/v1";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function redirectToLogin(): void {
  if (window.location.pathname !== "/login") {
    window.location.assign("/login");
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const token = getToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let response: Response;
  try {
    response = await fetch(API_ROOT + path, { ...init, headers });
  } catch {
    throw new ApiError(
      `Cannot reach the backend at ${API_ROOT}. Is the API running?`,
    );
  }

  let data: unknown = null;
  try {
    data = await response.json();
  } catch {
    // Non-JSON response body — leave null.
  }

  if (!response.ok) {
    if (response.status === 401 && path !== "/auth/login") {
      clearToken();
      redirectToLogin();
    }
    const body = data as {
      error?: { message?: string };
      detail?: string | Record<string, unknown>;
    } | null;
    const message =
      (body?.error && body.error.message) ||
      (body?.detail &&
        (typeof body.detail === "string" ? body.detail : "Invalid request")) ||
      `Request failed (HTTP ${response.status})`;
    throw new ApiError(message, response.status);
  }

  return data as T;
}

function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

function del<T>(path: string): Promise<T> {
  return request<T>(path, { method: "DELETE" });
}

async function uploadFile(
  path: string,
  formData: FormData,
  onProgress?: (percent: number) => void,
): Promise<DocumentUploadResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", API_ROOT + path);
    const token = getToken();
    if (token) {
      xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    }
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };
    xhr.onload = () => {
      let data: DocumentUploadResponse | null = null;
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        // No body
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(data as DocumentUploadResponse);
      } else {
        if (xhr.status === 401) {
          clearToken();
          redirectToLogin();
        }
        const body = data as unknown as {
          error?: { message?: string };
          detail?: string;
        } | null;
        const message =
          (body?.error && body.error.message) ||
          (body?.detail as string) ||
          `Upload failed (HTTP ${xhr.status})`;
        reject(new ApiError(message, xhr.status));
      }
    };
    xhr.onerror = () => reject(new ApiError("Upload failed — network error."));
    xhr.send(formData);
  });
}

export const api = {
  /* Auth */
  login: (email: string, password: string) =>
    post<TokenResponse>("/auth/login", { email, password }),
  register: (body: RegisterRequest) =>
    post<TokenResponse>("/auth/register", body),
  authMethods: () => request<AuthMethods>("/auth/methods"),
  exchangeGoogleCode: (code: string) =>
    post<TokenResponse>("/auth/google/exchange", { code }),
  googleStartUrl: () => `${API_ROOT}/auth/google/start`,
  me: () => request<UserRead>("/auth/me"),
  logoutLocally: () => {
    clearToken();
  },

  /* Dashboard */
  dashboard: () => request<DashboardResponse>("/dashboard"),

  /* Documents */
  listDocuments: () => request<DocumentOverviewListResponse>("/documents"),
  getDocumentOverview: (id: UUID) =>
    request<DocumentOverview>(`/documents/${encodeURIComponent(id)}/overview`),
  getDocumentStructure: (id: UUID) =>
    request<DocumentStructureResponse>(`/documents/${encodeURIComponent(id)}/structure`),
  extractDocument: (id: UUID) =>
    post<PageExtractionResponse>(`/documents/${encodeURIComponent(id)}/extract`),
  detectStructure: (id: UUID) =>
    post<DocumentStructureResponse>(`/documents/${encodeURIComponent(id)}/detect-structure`),
  chunkDocument: (id: UUID) =>
    post<ChunkingResponse>(`/documents/${encodeURIComponent(id)}/chunk`),
  analyzeDocument: (id: UUID) =>
    post<TopicAnalysisResponse>(`/documents/${encodeURIComponent(id)}/analyze`),
  listTopics: (id: UUID) =>
    request<TopicRead[]>(`/documents/${encodeURIComponent(id)}/topics`),
  buildDependencies: (id: UUID) =>
    post<DependencyGraphResponse>(`/documents/${encodeURIComponent(id)}/dependencies`),
  canonicalizeDocument: (id: UUID) =>
    post<CanonicalizationResponse>(`/documents/${encodeURIComponent(id)}/canonicalize`),

  /* Content QA */
  runQA: (curriculumId: UUID) =>
    post<QAReportResponse>(`/curricula/${encodeURIComponent(curriculumId)}/qa`),
  getQualityReport: (curriculumId: UUID) =>
    request<QAReportRead>(`/curricula/${encodeURIComponent(curriculumId)}/quality-report`),
  getCoverageReport: (curriculumId: UUID) =>
    request<CoverageReportRead>(`/curricula/${encodeURIComponent(curriculumId)}/coverage`),

  /* Assessments */
  generateUnitAssessment: (
    curriculumId: UUID,
    unitId: UUID,
    body: AssessmentGenerateRequest = {},
  ) =>
    post<AssessmentRead>(
      `/curricula/${encodeURIComponent(curriculumId)}/units/${encodeURIComponent(unitId)}/assessments`,
      body,
    ),
  generateFinalAssessment: (
    curriculumId: UUID,
    body: AssessmentGenerateRequest = {},
  ) =>
    post<AssessmentRead>(
      `/curricula/${encodeURIComponent(curriculumId)}/assessments/final`,
      body,
    ),
  listUnitAssessments: (curriculumId: UUID, unitId: UUID) =>
    request<AssessmentListResponse>(
      `/curricula/${encodeURIComponent(curriculumId)}/units/${encodeURIComponent(unitId)}/assessments`,
    ),
  listCurriculumAssessments: (curriculumId: UUID) =>
    request<AssessmentListResponse>(
      `/curricula/${encodeURIComponent(curriculumId)}/assessments`,
    ),
  getAssessment: (assessmentId: UUID) =>
    request<AssessmentRead>(`/assessments/${encodeURIComponent(assessmentId)}`),
  reviewAssessment: (assessmentId: UUID, body: AssessmentReviewRequest) =>
    post<AssessmentRead>(`/assessments/${encodeURIComponent(assessmentId)}/review`, body),

  /* Upload (progress-aware) */
  uploadDocument: (
    file: File,
    onProgress?: (percent: number) => void,
  ) => {
    const formData = new FormData();
    formData.append("file", file);
    return uploadFile("/documents", formData, onProgress);
  },

  /* Ingestion jobs */
  createIngestionJob: (documentId: UUID) =>
    post<IngestionJobCreateResponse>("/ingestion/jobs", { document_id: documentId }),
  getIngestionJob: (id: UUID) =>
    request<IngestionJobRead>(`/ingestion/jobs/${encodeURIComponent(id)}`),
  cancelIngestionJob: (id: UUID) =>
    post<IngestionJobRead>(`/ingestion/jobs/${encodeURIComponent(id)}/cancel`),

  /* Topics */
  getTopicProvenance: (id: UUID) =>
    request<TopicProvenanceResponse>(`/topics/${encodeURIComponent(id)}/provenance`),

  /* Curriculum */
  generateCurriculum: (body: CurriculumGenerateRequest) =>
    post<CurriculumGenerateResponse>("/curricula", body),
  listCurricula: (documentId: UUID) =>
    request<CurriculumListResponse>(`/curricula?document_id=${encodeURIComponent(documentId)}`),
  getCurriculum: (id: UUID) =>
    request<CurriculumDetailRead>(`/curricula/${encodeURIComponent(id)}`),
  submitCurriculumForReview: (id: UUID) =>
    post<CurriculumDetailRead>(`/curricula/${encodeURIComponent(id)}/submit-for-review`),
  reviewCurriculum: (id: UUID, body: CurriculumReviewRequest) =>
    post<CurriculumDetailRead>(`/curricula/${encodeURIComponent(id)}/review`, body),

  /* Course content (lessons) */
  generateWeekContent: (unitId: UUID) =>
    post<GenerateWeekResponse>(`/course-content/weeks/${encodeURIComponent(unitId)}/generate`),
  listWeekLessons: (unitId: UUID) =>
    request<LessonListResponse>(`/course-content/weeks/${encodeURIComponent(unitId)}/lessons`),
  getLesson: (lessonId: UUID) =>
    request<LessonRead>(`/course-content/lessons/${encodeURIComponent(lessonId)}`),
  getLessonSourceMap: (lessonId: UUID) =>
    request<LessonSourceMapRead>(
      `/course-content/lessons/${encodeURIComponent(lessonId)}/source-map`,
    ),
  submitLessonForReview: (lessonId: UUID) =>
    post<LessonRead>(`/course-content/lessons/${encodeURIComponent(lessonId)}/submit-for-review`),
  reviewLesson: (lessonId: UUID, body: LessonReviewRequest) =>
    post<LessonRead>(`/course-content/lessons/${encodeURIComponent(lessonId)}/review`, body),
  reviewBlock: (blockId: UUID, body: BlockReviewRequest) =>
    post<LessonBlockRead>(`/course-content/blocks/${encodeURIComponent(blockId)}/review`, body),
  regenerateBlock: (blockId: UUID) =>
    post<LessonBlockRead>(`/course-content/blocks/${encodeURIComponent(blockId)}/regenerate`),
  deleteBlock: (blockId: UUID) =>
    del<void>(`/course-content/blocks/${encodeURIComponent(blockId)}`),

  /* Bulk generation across every week of a curriculum */
  generateAllLessons: (curriculumId: UUID, rebuildExisting = false) =>
    post<ContentGenerationCreateResponse>(
      `/course-content/curricula/${encodeURIComponent(curriculumId)}/generate-all`,
      { rebuild_existing: rebuildExisting },
    ),
  getContentGenerationJob: (curriculumId: UUID) =>
    request<ContentGenerationJob | null>(
      `/course-content/curricula/${encodeURIComponent(curriculumId)}/generate-all`,
    ),

  /* Moodle */
  moodleStatus: () => request<MoodleConnectionStatus>("/moodle/status"),
  moodleCheck: () => request<MoodleConnectionCheck>("/moodle/check"),
  moodlePreflight: () => request<MoodlePreflightResponse>("/moodle/preflight"),
  exportCurriculum: (curriculumId: UUID) =>
    request<MoodleReadyExport>(
      `/curricula/${encodeURIComponent(curriculumId)}/export`,
    ),
  publishCurriculum: (curriculumId: UUID, body: MoodlePublishRequest) =>
    post<MoodlePublishResponse>(`/moodle/publish/${encodeURIComponent(curriculumId)}`, body),
  listCourses: () => request<MoodleCourseListResponse>("/courses"),
  verifyCourse: (courseId: UUID) =>
    post<MoodleVerifyResponse>(`/moodle/verify/${courseId}`),
};
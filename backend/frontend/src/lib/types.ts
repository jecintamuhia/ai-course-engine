export type UUID = string;

export type IngestionState =
  | "pending"
  | "validating"
  | "extracting"
  | "normalizing"
  | "structuring"
  | "chunking"
  | "analyzing"
  | "knowledge_building"
  | "planning"
  | "validating_output"
  | "awaiting_review"
  | "approved"
  | "publishing"
  | "completed"
  | "failed"
  | "cancelled";

export type CurriculumStatus =
  | "draft"
  | "awaiting_review"
  | "approved"
  | "rejected"
  | "published";

export type CourseStatus = "synced" | "sync_failed";

export type SourceType = "source_derived" | "ai_generated" | "ai_enriched";

export interface DocumentRead {
  id: UUID;
  original_filename: string;
  mime_type: string;
  file_extension: string;
  size_bytes: number;
  sha256_hash: string;
  version_number: number;
  is_latest_version: boolean;
  previous_version_id: UUID | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface DocumentUploadResponse {
  document: DocumentRead;
  is_duplicate: boolean;
}

export interface IngestionJobRead {
  id: UUID;
  document_id: UUID;
  status: IngestionState;
  correlation_id: string;
  attempt_count: number;
  max_attempts: number;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface IngestionJobCreateResponse {
  job: IngestionJobRead;
  created: boolean;
}

export interface DocumentOverview {
  document: DocumentRead;
  page_count: number;
  chapter_count: number;
  chunk_count: number;
  topic_count: number;
  curriculum_count: number;
  latest_job: IngestionJobRead | null;
}

export interface DocumentOverviewListResponse {
  documents: DocumentOverview[];
}

export interface ConceptRead {
  id: UUID;
  name: string;
  description: string;
  order_index: number;
  source_type: SourceType;
}

export interface TopicRead {
  id: UUID;
  document_id: UUID;
  chapter_id: UUID | null;
  parent_topic_id: UUID | null;
  title: string;
  learning_objectives: string[];
  prerequisite_titles: string[];
  difficulty: number;
  estimated_workload_minutes: number;
  order_index: number;
  source_type: SourceType;
  concepts: ConceptRead[];
  subtopics: TopicRead[];
  created_at: string;
}

export interface TopicAnalysisResponse {
  document_id: UUID;
  topic_count: number;
  topics: TopicRead[];
}

export interface ChunkRead {
  id: UUID;
  document_id: UUID;
  page_id: UUID;
  chapter_id: UUID | null;
  section_id: UUID | null;
  document_index: number;
  page_index: number;
  content: string;
  char_count: number;
  content_hash: string;
}

export interface ChunkingResponse {
  document_id: UUID;
  chunk_count: number;
  chunks: ChunkRead[];
}

export interface PageRead {
  id: UUID;
  document_id: UUID;
  page_number: number;
  normalized_text: string;
  char_count: number;
  created_at: string;
}

export interface PageExtractionResponse {
  document_id: UUID;
  page_count: number;
  pages: PageRead[];
}

export interface SectionRead {
  id: UUID;
  number: string | null;
  title: string;
  start_page: number;
  end_page: number;
  order_index: number;
}

export interface ChapterRead {
  id: UUID;
  number: string | null;
  title: string;
  start_page: number;
  end_page: number;
  order_index: number;
  sections: SectionRead[];
}

export interface DocumentStructureResponse {
  document_id: UUID;
  chapters: ChapterRead[];
}

export interface ProvenanceChunkRead {
  chunk_id: UUID;
  chunk_content: string;
  page_id: UUID;
  page_number: number;
}

export interface TopicProvenanceResponse {
  topic_id: UUID;
  topic_title: string;
  source_type: SourceType;
  source_chunks: ProvenanceChunkRead[];
}

export interface RejectedCycleEdge {
  topic_id: UUID;
  depends_on_topic_id: UUID;
}

export interface UnresolvedPrerequisiteRead {
  topic_id: UUID;
  topic_title: string;
  prerequisite_title: string;
  reason: string;
}

export interface DependencyGraphResponse {
  document_id: UUID;
  topological_order: UUID[];
  rejected_cycle_edges: RejectedCycleEdge[];
  unresolved_prerequisites: UnresolvedPrerequisiteRead[];
}

export interface CurriculumUnitTopicRead {
  topic_id: UUID;
  title: string;
  order_index: number;
}

export interface CurriculumUnitRead {
  id: UUID;
  week_number: number;
  title: string;
  description: string;
  learning_objectives: string[];
  estimated_workload_minutes: number;
  order_index: number;
  topics: CurriculumUnitTopicRead[];
}

export interface CurriculumRead {
  id: UUID;
  document_id: UUID;
  title: string;
  description: string | null;
  status: CurriculumStatus;
  total_weeks: number;
  start_date: string | null;
  learning_days_per_week: number;
  hours_per_day: number;
  max_weekly_workload_minutes: number;
  min_topic_allocation_minutes: number;
  max_topic_allocation_minutes: number;
  version_number: number;
  is_latest_version: boolean;
  created_at: string;
  units: CurriculumUnitRead[];
}

export interface CurriculumGenerateRequest {
  document_id: UUID;
  total_weeks?: number;
  learning_days_per_week?: number;
  hours_per_day?: number;
  start_date?: string | null;
  title?: string | null;
  description?: string | null;
}

export interface CurriculumGenerateResponse {
  curriculum: CurriculumRead;
}

export interface CurriculumReviewRead {
  id: UUID;
  curriculum_id: UUID;
  reviewer_name: string | null;
  decision: "approved" | "rejected";
  comments: string | null;
  reviewed_at: string;
}

export interface CurriculumDetailRead extends CurriculumRead {
  reviews: CurriculumReviewRead[];
}

export interface CurriculumListResponse {
  curricula: CurriculumRead[];
}

export interface CurriculumReviewRequest {
  decision: "approved" | "rejected";
  reviewer_name?: string | null;
  comments?: string | null;
}

export interface MoodleConnectionStatus {
  configured: boolean;
  moodle_url: string | null;
  connected: boolean;
  site_name: string | null;
  site_url: string | null;
  api_version: string | null;
  username: string | null;
  error: string | null;
}

export interface MoodleConnectionCheck extends MoodleConnectionStatus {
  default_category_id: number | null;
  default_category_found: boolean | null;
  categories_visible: number;
}

export interface MoodlePublishRequest {
  idnumber?: string | null;
  fullname?: string | null;
  shortname?: string | null;
  category_id?: number | null;
}

export interface MoodleCourseRead {
  id: string;
  curriculum_id: string;
  title: string;
  fullname: string;
  shortname: string;
  idnumber: string;
  moodle_course_id: number | null;
  moodle_url: string | null;
  status: CourseStatus;
  sections_published: number;
  resources_published: number;
  last_sync_at: string | null;
  sync_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface MoodleCourseListResponse {
  courses: MoodleCourseRead[];
}

export interface MoodlePublishResponse {
  course_id: string;
  moodle_course_id: number;
  course_fullname: string;
  course_shortname: string;
  course_url: string;
  idnumber: string;
  created: boolean;
  sections_published: number;
  resources_published: number;
  verified: boolean;
}

export interface MoodleVerifyResponse {
  course_id: string;
  moodle_course_id: number | null;
  found: boolean;
  sections_found: number;
  modules_found: number;
  section_names: string[];
  course_url: string | null;
  error: string | null;
}

export interface MoodlePreflightIssue {
  kind: string;
  message: string;
  admin_action: string;
  ws_function: string | null;
  capability: string | null;
  recoverable: boolean;
}

export interface MoodlePreflightCheck {
  label: string;
  status: "ok" | "warning" | "error";
  detail: string;
  verification: "direct" | "inferred" | "not_verifiable";
  ws_function: string | null;
  capability: string | null;
}

export interface MoodlePreflightResponse {
  ready: boolean;
  configured: boolean;
  moodle_url: string | null;
  site_name: string | null;
  site_url: string | null;
  api_version: string | null;
  username: string | null;
  functions_available: string[];
  functions_required: string[];
  capabilities_required: string[];
  category_id: number | null;
  category_found: boolean | null;
  checks: MoodlePreflightCheck[];
  issues: MoodlePreflightIssue[];
  blocking_issues: MoodlePreflightIssue[];
  checked_at: string;
}

export interface MoodleReadyExportTopic {
  title: string;
  learning_objectives: string[];
  prerequisite_titles: string[];
  difficulty: number;
  estimated_workload_minutes: number;
  source_type: string | null;
}

export interface MoodleReadyExportWeek {
  week_number: number;
  title: string;
  description: string;
  learning_objectives: string[];
  estimated_workload_minutes: number;
  topics: MoodleReadyExportTopic[];
}

export interface MoodleReadyExport {
  format: string;
  version: number;
  generated_at: string;
  importable: boolean;
  notes: string;
  curriculum: {
    id: string;
    version_number: number;
    status: string;
    title: string;
    description: string | null;
    total_weeks: number;
    learning_days_per_week: number;
    hours_per_day: number;
    max_weekly_workload_minutes: number;
  };
  source: {
    document_id: string;
    document_filename: string | null;
    provenance: string;
  };
  weeks: MoodleReadyExportWeek[];
}

export interface DashboardResponse {
  documents_total: number;
  documents_processing: number;
  curricula_total: number;
  curricula_pending_review: number;
  curricula_approved: number;
  curricula_published: number;
  courses_published: number;
  moodle: MoodleConnectionStatus | null;
}

export interface ApiErrorBody {
  error?: { code?: string; message?: string; details?: unknown };
  detail?: string | Record<string, unknown>;
}

/** Persisted upload / curriculum-generation preferences for a document. */
export interface DraftPreferences {
  title: string | null;
  description: string | null;
  shortname: string | null;
  category_id: number | null;
  total_weeks: number;
  learning_days_per_week: number;
}
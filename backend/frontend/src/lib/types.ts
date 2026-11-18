export type UUID = string;

export type UserRole = "admin" | "lecturer" | "student" | "teacher";

export interface UserRead {
  id: UUID;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: UserRead;
  redirect_to: string;
}

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

export type LessonStatus =
  | "draft"
  | "generating"
  | "failed"
  | "awaiting_review"
  | "approved"
  | "rejected";

export type BlockReviewStatus = "generated" | "approved" | "rejected";

export type LessonBlockType =
  | "text"
  | "heading"
  | "example"
  | "diagram"
  | "table"
  | "external_resource"
  | "video"
  | "activity"
  | "knowledge_check"
  | "summary"
  | "practical_task";

/** Lifecycle of a practical task hand-in. */
export type SubmissionStatus = "submitted" | "graded" | "needs_revision";

/** The kinds of learner activity a lecturer sees on the feed. */
export type LecturerActivityType =
  | "enrolled"
  | "withdrew"
  | "lesson_completed"
  | "submission_received"
  | "submission_graded"
  | "submission_returned";

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

export interface MoodleModuleRead {
  cmid: number;
  name: string;
  modname: string;
  content: string | null;
  content_format: number | null;
  url: string | null;
  lesson_id: UUID | null;
}

export interface MoodleSectionRead {
  section_number: number;
  name: string;
  summary: string | null;
  modules: MoodleModuleRead[];
}

export interface MoodleCourseStructureRead {
  course_id: UUID;
  moodle_course_id: number;
  moodle_url: string | null;
  title: string;
  fullname: string;
  shortname: string;
  sections: MoodleSectionRead[];
}

export interface MoodleLessonContentRead {
  course_id: UUID;
  lesson_id: UUID;
  title: string;
  content_html: string;
  content_format: number | null;
  page_name: string | null;
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

export interface LessonBlockRead {
  id: UUID;
  lesson_id: UUID;
  block_type: LessonBlockType;
  order_index: number;
  title: string | null;
  payload: Record<string, unknown>;
  review_status: BlockReviewStatus;
  review_comments: string | null;
  created_at: string;
  updated_at: string;
}

export interface LessonRead {
  id: UUID;
  curriculum_id: UUID;
  curriculum_unit_id: UUID;
  topic_id: UUID | null;
  week_number: number;
  order_index: number;
  title: string;
  description: string;
  learning_objectives: string[];
  estimated_workload_minutes: number;
  status: LessonStatus;
  generation_errors: { component?: string; reason?: string; message?: string }[];
  created_at: string;
  updated_at: string;
  blocks: LessonBlockRead[];
}

export interface LessonListResponse {
  curriculum_unit_id: UUID;
  lessons: LessonRead[];
}

export interface GenerateWeekResponse {
  curriculum_unit_id: UUID;
  generated: LessonRead[];
  skipped: { topic_id?: UUID; reason?: string }[];
  errors: { component?: string; reason?: string }[];
}

export type ContentGenerationStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export interface ContentGenerationJob {
  id: UUID;
  curriculum_id: UUID;
  status: ContentGenerationStatus;
  correlation_id: string;
  total_weeks: number;
  completed_weeks: number;
  lessons_generated: number;
  skipped_weeks: number;
  failed_weeks: number;
  rebuild_existing: boolean;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface ContentGenerationCreateResponse {
  job: ContentGenerationJob;
  created: boolean;
}

export interface RegisterRequest {
  email: string;
  password: string;
  full_name: string;
}

export interface AuthMethods {
  google_enabled: boolean;
  registration_enabled: boolean;
  allowed_domains: string[];
}

/** The signed-in learner's own account, as the portal sees it. */
export interface LearnerProfileRead {
  id: UUID;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

/** A published course a learner can open in Moodle. */
export interface LearnerCourseRead {
  id: UUID;
  title: string;
  fullname: string;
  shortname: string;
  moodle_course_id: number | null;
  moodle_url: string | null;
  status: CourseStatus;
  sections_published: number;
  resources_published: number;
  last_sync_at: string | null;
}

export interface LearnerCourseListResponse {
  courses: LearnerCourseRead[];
}

/** Result of an enrol or withdraw action. */
export interface LearnerEnrolmentResponse {
  enrolled: boolean;
  enrolment_id: UUID | null;
}

/** One completed lesson inside a learner's enrolment. */
export interface LearnerMilestoneRead {
  id: UUID;
  enrolment_id: UUID;
  lesson_id: UUID;
  completed_at: string;
}

/** A learner's hand-in for a practical task block. */
export interface PracticalSubmissionRead {
  id: UUID;
  enrolment_id: UUID;
  block_id: UUID;
  lesson_id: UUID;
  content: string;
  status: SubmissionStatus;
  grade: number | null;
  feedback: string | null;
  submitted_at: string;
  graded_at: string | null;
  graded_by_id: UUID | null;
}

/** The learner submission API wraps one submission in an envelope. */
export interface PracticalSubmissionResponse {
  submission: PracticalSubmissionRead;
}

/** A content block as the learner sees it, with their own submission. */
export interface LearnerBlockRead {
  id: UUID;
  lesson_id: UUID;
  block_type: LessonBlockType;
  order_index: number;
  title: string | null;
  payload: Record<string, unknown>;
  review_status: BlockReviewStatus;
  submission: PracticalSubmissionRead | null;
}

/** A lesson as the learner sees it, with its blocks and completion state. */
export interface LearnerLessonRead {
  id: UUID;
  curriculum_id: UUID;
  curriculum_unit_id: UUID;
  week_number: number;
  order_index: number;
  title: string;
  description: string;
  learning_objectives: string[];
  estimated_workload_minutes: number;
  status: LessonStatus;
  blocks: LearnerBlockRead[];
  completed: boolean;
}

/** How far through a course a learner is. */
export interface LearnerProgressSummary {
  total_lessons: number;
  completed_lessons: number;
  percentage: number;
}

/** A course with its lessons and the learner's own progress. */
export interface LearnerCourseDetailRead {
  course: LearnerCourseRead;
  lessons: LearnerLessonRead[];
  milestones: LearnerMilestoneRead[];
  progress: LearnerProgressSummary;
  enrolled: boolean;
}

/** Result of marking a lesson complete or undoing it. */
export interface LearnerLessonCompletionResponse {
  completed: boolean;
  milestone_id: UUID | null;
}

/** One learner row on the lecturer's progress view. */
export interface LecturerLearnerProgress {
  enrolment_id: UUID;
  user_id: UUID;
  full_name: string;
  email: string;
  enrolled_at: string;
  completed_lessons: number;
  total_lessons: number;
  percentage: number;
  submission_count: number;
}

/** One entry on the lecturer's activity feed. */
export interface LecturerActivityRead {
  id: UUID;
  course_id: UUID;
  actor_user_id: UUID | null;
  subject_user_id: UUID | null;
  event_type: LecturerActivityType;
  summary: string;
  details: Record<string, unknown>;
  created_at: string;
}

/** The mark and feedback a lecturer leaves on a submission. */
export interface LecturerGradeRequest {
  grade?: number | null;
  feedback?: string | null;
}

export interface LessonReviewRequest {
  decision: "approved" | "rejected";
  reviewer_name?: string | null;
  comments?: string | null;
}

export interface BlockReviewRequest {
  review_status: "approved" | "rejected";
  comments?: string | null;
}

export interface SourceMapBlockCitation {
  block_id: UUID;
  block_type: LessonBlockType;
  title: string | null;
  order_index: number;
}

export interface SourceMapItem {
  chunk_id: UUID;
  page_number: number | null;
  document_index: number;
  content: string;
  cited_by: SourceMapBlockCitation[];
}

export interface LessonSourceMapRead {
  lesson_id: UUID;
  sources: SourceMapItem[];
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

export type QAVerdict = "pass" | "warning" | "fail";
export type FindingSeverity = "error" | "warning" | "info";

export interface QALocation {
  kind: string;
  id: UUID | null;
  title: string | null;
  detail: string | null;
}

export interface QAFinding {
  rule: string;
  code: string;
  severity: FindingSeverity;
  message: string;
  locations: QALocation[];
}

export interface QAAreaStatus {
  status: QAVerdict;
  findings: number;
}

export interface QAReportRead {
  id: UUID;
  curriculum_id: UUID;
  version_number: number;
  verdict: QAVerdict;
  areas: Record<string, QAAreaStatus>;
  findings: QAFinding[];
  summary: Record<string, number>;
  checked_at: string;
}

export interface QAReportResponse {
  report: QAReportRead;
  blocked: boolean;
}

export interface TopicCoverageItem {
  topic_id: UUID;
  title: string;
  chapter_id: UUID | null;
  chapter_title: string | null;
  importance: string | null;
  workload_minutes: number;
  sources_chapters: number;
  mapped: boolean;
  has_lesson: boolean;
}

export interface CoverageReportRead {
  document_id: UUID;
  document_title: string;
  curriculum_id: UUID | null;
  chapters: number;
  sections: number;
  topic_count: number;
  importance_counts: Record<string, number>;
  mapped_topic_count: number;
  lesson_count: number;
  coverage_percent: number;
  duplicate_topics_removed: number;
  unresolved_topic_count: number;
  unresolved_topics: string[];
  resource_count: number;
  video_count: number;
  activity_count: number;
  knowledge_check_count: number;
  diagram_count: number;
  topics: TopicCoverageItem[];
}

export interface CanonicalTopicRead {
  id: UUID;
  chapter_id: UUID | null;
  title: string;
  canonical_key: string;
  aliases: string[];
  importance: string | null;
  order_index: number;
  parent_topic_id: UUID | null;
}

export interface DuplicateTopicRead {
  id: UUID;
  title: string;
  duplicate_of_id: UUID;
}

export interface CanonicalizationResponse {
  document_id: UUID;
  topics_seen: number;
  clusters: number;
  duplicates_flagged: number;
  aliases_created: number;
  canonical: CanonicalTopicRead[];
  duplicates: DuplicateTopicRead[];
  near_duplicates: { left: string; right: string; similarity: number }[];
  canonicalized_at: string;
}

export type AssessmentType =
  | "weekly_quiz"
  | "practical_assignment"
  | "coding_task"
  | "case_study"
  | "mini_project"
  | "final";

export type AssessmentStatus =
  | "draft"
  | "generating"
  | "awaiting_review"
  | "approved"
  | "rejected";

export interface AssessmentOptionRead {
  id: string;
  text: string;
}

export interface AssessmentItemRead {
  kind: string;
  prompt: string;
  learning_objective: string;
  difficulty: "easy" | "medium" | "hard";
  options: AssessmentOptionRead[];
  correct_option_id: string | null;
  correct_answer: string | null;
  explanation: string;
  rubric: string | null;
  source_chunk_markers: string[];
}

export interface AssessmentAlignmentRead {
  learning_objective: string;
  lesson_id: UUID | null;
  lesson_title: string | null;
  unit_week: number | null;
  evidence: string[];
}

export interface AssessmentRead {
  id: UUID;
  curriculum_id: UUID;
  curriculum_unit_id: UUID | null;
  week_number: number | null;
  title: string;
  description: string;
  assessment_type: AssessmentType;
  learning_objectives: string[];
  estimated_minutes: number;
  items: AssessmentItemRead[];
  alignment: AssessmentAlignmentRead[];
  status: AssessmentStatus;
  generation_errors: { component?: string; reason?: string; message?: string }[];
  reviewer_name: string | null;
  review_comments: string | null;
  created_at: string;
}

export interface AssessmentListResponse {
  assessments: AssessmentRead[];
}

export interface AssessmentGenerateRequest {
  assessment_type?: AssessmentType | null;
  max_items?: number;
}

export interface AssessmentReviewRequest {
  decision: "approved" | "rejected";
  reviewer_name?: string | null;
  comments?: string | null;
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

export type LearnerAssessmentItemKind =
  | "multiple_choice"
  | "true_false"
  | "short_answer"
  | "scenario"
  | "practical"
  | "coding"
  | "matching";

export interface LearnerAssessmentQuestion {
  item_index: number;
  kind: LearnerAssessmentItemKind;
  prompt: string;
  learning_objective: string;
  difficulty: "easy" | "medium" | "hard";
  options: AssessmentOptionRead[];
  auto_gradable: boolean;
}

export interface LearnerAssessmentAttemptSummary {
  id: UUID;
  attempt_number: number;
  score_percent: number;
  correct_count: number;
  auto_gradable_count: number;
  passed: boolean;
  submitted_at: string;
}

export interface LearnerCertificateSummary {
  reference: string;
  issued_at: string;
  score_percent: number;
}

export interface LearnerFinalAssessmentRead {
  assessment_id: UUID;
  title: string;
  description: string;
  estimated_minutes: number;
  pass_percent: number;
  questions: LearnerAssessmentQuestion[];
  auto_gradable_count: number;
  total_items: number;
  completed_lessons: number;
  total_lessons: number;
  all_lessons_completed: boolean;
  attempts: LearnerAssessmentAttemptSummary[];
  best_score_percent: number | null;
  best_attempt_id: UUID | null;
  passed: boolean;
  certificate: LearnerCertificateSummary | null;
}

export interface LearnerAssessmentAnswer {
  item_index: number;
  option_id?: string | null;
  answer?: string | null;
}

export interface LearnerAssessmentItemResult {
  item_index: number;
  kind: LearnerAssessmentItemKind;
  prompt: string;
  answered: boolean;
  auto_graded: boolean;
  correct: boolean | null;
  submitted_option_id: string | null;
  submitted_answer: string | null;
  correct_option_id: string | null;
  correct_answer: string | null;
  explanation: string;
}

export interface LearnerAssessmentAttemptRead {
  id: UUID;
  assessment_id: UUID;
  attempt_number: number;
  score_percent: number;
  correct_count: number;
  auto_gradable_count: number;
  passed: boolean;
  submitted_at: string;
  results: LearnerAssessmentItemResult[];
}

export interface LearnerAssessmentAttemptListResponse {
  attempts: LearnerAssessmentAttemptRead[];
}

export interface LearnerCertificateRead {
  reference: string;
  learner_name: string;
  course_title: string;
  score_percent: number;
  completed_lessons: number;
  total_lessons: number;
  issued_at: string;
}

export interface LearnerCertificateCourseRead extends LearnerCertificateRead {
  course_id: UUID;
}

export interface LearnerCertificateListResponse {
  certificates: LearnerCertificateCourseRead[];
}

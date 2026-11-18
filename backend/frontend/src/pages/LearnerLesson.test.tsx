import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { LearnerLessonPage } from "@/pages/LearnerLesson";
import { api } from "@/lib/api";
import type {
  LearnerCourseDetailRead,
  MoodleLessonContentRead,
} from "@/lib/types";

vi.mock("@/lib/api", () => ({
  api: {
    learnerCourseDetail: vi.fn(),
    learnerLessonContent: vi.fn(),
    learnerCompleteLesson: vi.fn(),
    learnerUncompleteLesson: vi.fn(),
    learnerSubmitPractical: vi.fn(),
  },
}));

const courseId = "11111111-1111-1111-1111-111111111111";
const lessonId = "22222222-2222-2222-2222-222222222222";
const otherLessonId = "33333333-3333-3333-3333-333333333333";

const courseDetail = {
  course: {
    id: courseId,
    title: "Hosting Administration",
    fullname: "Hosting Administration",
    shortname: "hosting",
    moodle_course_id: 7,
    moodle_url: "https://moodle.example.com/course/view.php?id=7",
    status: "synced",
    sections_published: 4,
    resources_published: 12,
    last_sync_at: "2026-11-01T00:00:00Z",
  },
  lessons: [
    {
      id: lessonId,
      curriculum_id: "44444444-4444-4444-4444-444444444444",
      curriculum_unit_id: "55555555-5555-5555-5555-555555555555",
      week_number: 1,
      order_index: 0,
      title: "Lesson One",
      description: "First lesson.",
      learning_objectives: ["Objective one."],
      estimated_workload_minutes: 30,
      status: "approved",
      blocks: [],
      completed: false,
    },
    {
      id: otherLessonId,
      curriculum_id: "44444444-4444-4444-4444-444444444444",
      curriculum_unit_id: "55555555-5555-5555-5555-555555555555",
      week_number: 1,
      order_index: 1,
      title: "Lesson Two",
      description: "Second lesson.",
      learning_objectives: [],
      estimated_workload_minutes: 30,
      status: "approved",
      blocks: [],
      completed: true,
    },
  ],
  milestones: [],
  progress: { total_lessons: 2, completed_lessons: 1, percentage: 50 },
  enrolled: true,
} as unknown as LearnerCourseDetailRead;

const lessonContent = {
  course_id: courseId,
  lesson_id: lessonId,
  title: "Lesson One",
  content_html: "<p>Read this first.</p>",
  content_format: 1,
  page_name: "Lesson One",
} as unknown as MoodleLessonContentRead;

function renderLessonPage(route: string) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route
          path="/learn/course/:courseId/lesson/:lessonId"
          element={<LearnerLessonPage />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("LearnerLessonPage back navigation", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders the lesson and links back to the course with one anchor", async () => {
    vi.mocked(api.learnerCourseDetail).mockResolvedValue(courseDetail);
    vi.mocked(api.learnerLessonContent).mockResolvedValue(lessonContent);

    renderLessonPage(`/learn/course/${courseId}/lesson/${lessonId}`);

    // The page loaded: lesson content is shown.
    expect(await screen.findByText("Read this first.")).toBeTruthy();

    // Regression: the "Back to <course>" button wraps a single Link even
    // though it renders an icon and a label, so Radix Slot does not crash.
    const back = screen.getByRole("link", {
      name: /back to hosting administration/i,
    });
    expect(back.getAttribute("href")).toBe(`/learn/course/${courseId}`);
    expect(back.querySelector("svg")).toBeTruthy();

    // It used the lesson-content endpoint for the right lesson.
    expect(api.learnerLessonContent).toHaveBeenCalledWith(courseId, lessonId);
    expect(api.learnerCourseDetail).toHaveBeenCalledWith(courseId);
  });

  it("links back to the course from the error state too", async () => {
    vi.mocked(api.learnerCourseDetail).mockResolvedValue(courseDetail);
    vi.mocked(api.learnerLessonContent).mockRejectedValue(
      new Error("Lesson not found."),
    );

    renderLessonPage(`/learn/course/${courseId}/lesson/${lessonId}`);

    const back = await screen.findByRole("link", { name: /back to course/i });
    expect(back.getAttribute("href")).toBe(`/learn/course/${courseId}`);
  });

  it("links to the next lesson when one follows", async () => {
    vi.mocked(api.learnerCourseDetail).mockResolvedValue(courseDetail);
    vi.mocked(api.learnerLessonContent).mockResolvedValue(lessonContent);

    renderLessonPage(`/learn/course/${courseId}/lesson/${lessonId}`);

    const next = await screen.findByRole("link", { name: /next lesson/i });
    expect(next.getAttribute("href")).toBe(
      `/learn/course/${courseId}/lesson/${otherLessonId}`,
    );
  });

  it("recovers from a failed lesson load when the learner retries", async () => {
    vi.mocked(api.learnerCourseDetail).mockResolvedValue(courseDetail);
    vi.mocked(api.learnerLessonContent)
      .mockRejectedValueOnce(new Error("Moodle timed out."))
      .mockResolvedValueOnce(lessonContent);

    renderLessonPage(`/learn/course/${courseId}/lesson/${lessonId}`);

    const retry = await screen.findByRole("button", { name: /try again/i });
    fireEvent.click(retry);

    expect(await screen.findByText("Read this first.")).toBeTruthy();
    expect(api.learnerLessonContent).toHaveBeenCalledTimes(2);
  });
});

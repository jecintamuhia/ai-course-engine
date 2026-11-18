import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { LecturerCoursePage } from "@/pages/LecturerCourse";
import { api } from "@/lib/api";
import type { MoodleCourseStructureRead } from "@/lib/types";

const staffState = vi.hoisted(() => ({ isStaff: true }));

vi.mock("@/lib/auth", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/auth")>();
  return { ...actual, isStaff: () => staffState.isStaff };
});

vi.mock("@/lib/api", () => ({
  api: {
    lecturerCourseContent: vi.fn(),
    lecturerLessonContent: vi.fn(),
  },
}));

const courseId = "99999999-9999-9999-9999-999999999999";
const lessonId = "22222222-2222-2222-2222-222222222222";

const structure = {
  course_id: courseId,
  moodle_course_id: 7,
  moodle_url: "https://moodle.example.com/course/view.php?id=7",
  title: "Hosting Administration",
  fullname: "Hosting Administration",
  shortname: "hosting",
  sections: [
    {
      section_number: 1,
      name: "Week 1",
      summary: null,
      modules: [
        {
          cmid: 101,
          name: "Lesson One",
          modname: "page",
          content: null,
          content_format: null,
          lesson_id: lessonId,
          url: "https://moodle.example.com/mod/page/view.php?id=101",
        },
      ],
    },
  ],
} as unknown as MoodleCourseStructureRead;

const lessonContent = {
  course_id: courseId,
  lesson_id: lessonId,
  title: "Lesson One",
  content_html: "<p>Lecturer lesson body.</p>",
  content_format: 1,
  page_name: "Lesson One",
};

function renderCoursePage(route: string) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route
          path="/lecturer/courses/:courseId"
          element={<LecturerCoursePage />}
        />
        <Route
          path="/lecturer/courses/:courseId/lessons/:lessonId"
          element={<LecturerCoursePage />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("LecturerCoursePage back navigation", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("links back to the review queue with one anchor per button", async () => {
    vi.mocked(api.lecturerCourseContent).mockResolvedValue(structure);

    renderCoursePage(`/lecturer/courses/${courseId}`);

    expect(await screen.findByText("Lesson One")).toBeTruthy();

    // Regression: the ghost "Back to review" button wraps a single Link
    // around icon + label, so Radix Slot does not crash.
    const back = screen.getByRole("link", { name: /back to review/i });
    expect(back.getAttribute("href")).toBe("/reviews");
    expect(back.querySelector("svg")).toBeTruthy();

    // The published course links out to Moodle in a new tab.
    const moodle = screen.getByRole("link", { name: /view on moodle/i });
    expect(moodle.getAttribute("href")).toBe(structure.moodle_url);
    expect(moodle.getAttribute("target")).toBe("_blank");
  });

  it("links back to the review queue from the error state", async () => {
    vi.mocked(api.lecturerCourseContent).mockRejectedValue(
      new Error("Course not found."),
    );

    renderCoursePage(`/lecturer/courses/${courseId}`);

    const back = await screen.findByRole("link", { name: /back to review/i });
    expect(back.getAttribute("href")).toBe("/reviews");
  });

  it("links non-staff back to the dashboard", async () => {
    staffState.isStaff = false;

    renderCoursePage(`/lecturer/courses/${courseId}`);

    // Regression: the restricted-view "Back to dashboard" button wraps a
    // single Link around icon + label, so Radix Slot does not crash.
    const back = await screen.findByRole("link", {
      name: /back to dashboard/i,
    });
    expect(back.getAttribute("href")).toBe("/dashboard");
    expect(back.querySelector("svg")).toBeTruthy();

    staffState.isStaff = true;
  });

  it("opens a lesson by its internal lesson id, not the Moodle cmid", async () => {
    vi.mocked(api.lecturerCourseContent).mockResolvedValue(structure);
    vi.mocked(api.lecturerLessonContent).mockResolvedValue(lessonContent);

    renderCoursePage(`/lecturer/courses/${courseId}`);

    fireEvent.click(await screen.findByRole("button", { name: /open lesson/i }));

    expect(await screen.findByText("Lecturer lesson body.")).toBeTruthy();
    expect(api.lecturerLessonContent).toHaveBeenCalledWith(courseId, lessonId);
    expect(api.lecturerLessonContent).not.toHaveBeenCalledWith(courseId, "101");
  });

  it("recovers when a lesson fails to load and the lecturer retries", async () => {
    vi.mocked(api.lecturerCourseContent).mockResolvedValue(structure);
    vi.mocked(api.lecturerLessonContent)
      .mockRejectedValueOnce(new Error("Moodle timed out."))
      .mockResolvedValueOnce(lessonContent);

    renderCoursePage(
      `/lecturer/courses/${courseId}/lessons/${lessonId}`,
    );

    const retry = await screen.findByRole("button", { name: /try again/i });
    fireEvent.click(retry);

    expect(await screen.findByText("Lecturer lesson body.")).toBeTruthy();
    expect(api.lecturerLessonContent).toHaveBeenCalledTimes(2);
  });

  it("does not offer to open a page that has no matching lesson", async () => {
    vi.mocked(api.lecturerCourseContent).mockResolvedValue({
      ...structure,
      sections: [
        {
          section_number: 1,
          name: "Week 1",
          summary: null,
          modules: [
            {
              cmid: 101,
              name: "Lesson One",
              modname: "page",
              content: null,
              content_format: null,
              lesson_id: null,
              url: "https://moodle.example.com/mod/page/view.php?id=101",
            },
          ],
        },
      ],
    } as unknown as MoodleCourseStructureRead);

    renderCoursePage(`/lecturer/courses/${courseId}`);

    const unavailable = await screen.findByRole("button", {
      name: /content not available/i,
    });
    expect((unavailable as HTMLButtonElement).disabled).toBe(true);
  });
});

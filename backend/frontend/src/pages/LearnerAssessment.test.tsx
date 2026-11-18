import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import {
  CertificateVerifyPage,
  LearnerAssessmentPage,
} from "@/pages/LearnerAssessment";
import { api } from "@/lib/api";
import type { LearnerFinalAssessmentRead } from "@/lib/types";

vi.mock("@/lib/api", () => ({
  ApiError: class ApiError extends Error {
    status: number;
    constructor(message: string, status = 0) {
      super(message);
      this.status = status;
    }
  },
  api: {
    learnerFinalAssessment: vi.fn(),
    learnerSubmitAssessment: vi.fn(),
    learnerRequestCertificate: vi.fn(),
    verifyCertificate: vi.fn(),
  },
}));

const courseId = "11111111-1111-1111-1111-111111111111";

function assessment(): LearnerFinalAssessmentRead {
  return {
    assessment_id: "22222222-2222-2222-2222-222222222222",
    title: "Final assessment",
    description: "Covers the whole course.",
    estimated_minutes: 60,
    pass_percent: 70,
    questions: [
      {
        item_index: 0,
        kind: "multiple_choice",
        prompt: "Which record keeps stock counts?",
        learning_objective: "Track inventory",
        difficulty: "easy",
        options: [
          { id: "a", text: "Inventory ledger" },
          { id: "b", text: "Payroll sheet" },
        ],
        auto_gradable: true,
      },
    ],
    auto_gradable_count: 1,
    total_items: 1,
    completed_lessons: 1,
    total_lessons: 1,
    all_lessons_completed: true,
    attempts: [],
    best_score_percent: null,
    best_attempt_id: null,
    passed: false,
    certificate: null,
  };
}

function renderAssessment() {
  return render(
    <MemoryRouter initialEntries={[`/learn/course/${courseId}/assessment`]}>
      <Routes>
        <Route
          path="/learn/course/:courseId/assessment"
          element={<LearnerAssessmentPage />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("LearnerAssessmentPage", () => {
  beforeEach(() => {
    vi.mocked(api.learnerFinalAssessment).mockResolvedValue(assessment());
    vi.mocked(api.learnerSubmitAssessment).mockResolvedValue({
      id: "33333333-3333-3333-3333-333333333333",
      assessment_id: "22222222-2222-2222-2222-222222222222",
      attempt_number: 1,
      score_percent: 100,
      correct_count: 1,
      auto_gradable_count: 1,
      passed: true,
      submitted_at: "2026-11-17T00:00:00Z",
      results: [
        {
          item_index: 0,
          kind: "multiple_choice",
          prompt: "Which record keeps stock counts?",
          answered: true,
          auto_graded: true,
          correct: true,
          submitted_option_id: "a",
          submitted_answer: null,
          correct_option_id: "a",
          correct_answer: "Inventory ledger",
          explanation: "An inventory ledger records stock movements.",
        },
      ],
    });
  });

  it("renders questions, submits the selected option and shows feedback", async () => {
    renderAssessment();

    expect(
      await screen.findByText(/Which record keeps stock counts\?/),
    ).toBeTruthy();
    fireEvent.click(screen.getByLabelText("Inventory ledger"));
    fireEvent.click(screen.getByRole("button", { name: "Submit attempt" }));

    await waitFor(() => {
      expect(api.learnerSubmitAssessment).toHaveBeenCalledWith(courseId, [
        { item_index: 0, option_id: "a" },
      ]);
    });
    expect(await screen.findByText(/You passed/)).toBeTruthy();
  });
});

describe("CertificateVerifyPage", () => {
  it("reports an unknown reference", async () => {
    vi.mocked(api.verifyCertificate).mockRejectedValue(new Error("missing"));

    render(
      <MemoryRouter initialEntries={["/verify/SKU-2026-NOPE"]}>
        <Routes>
          <Route path="/verify/:reference" element={<CertificateVerifyPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(
      await screen.findByText("No certificate matches that reference."),
    ).toBeTruthy();
  });
});

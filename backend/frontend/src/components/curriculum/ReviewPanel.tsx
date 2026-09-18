import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { curriculumBadge } from "@/lib/badges";
import { StatusBadge } from "@/components/shared/StatusBadge";
import type { CurriculumDetailRead } from "@/lib/types";
import { api } from "@/lib/api";
import { toast } from "sonner";

interface ReviewPanelProps {
  curriculum: CurriculumDetailRead;
  onUpdated: () => void;
}

export function ReviewPanel({ curriculum, onUpdated }: ReviewPanelProps) {
  const [reviewerName, setReviewerName] = useState("");
  const [comments, setComments] = useState("");
  const [loading, setLoading] = useState(false);

  const badge = curriculumBadge(curriculum.status);

  const handleSubmitForReview = async () => {
    setLoading(true);
    try {
      await api.submitCurriculumForReview(curriculum.id);
      toast.success("Submitted for lecturer review.");
      onUpdated();
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleReview = async (decision: "approved" | "rejected") => {
    setLoading(true);
    try {
      await api.reviewCurriculum(curriculum.id, {
        decision,
        reviewer_name: reviewerName.trim() || undefined,
        comments: comments.trim() || undefined,
      });
      toast.success(decision === "approved" ? "Curriculum approved." : "Curriculum rejected.");
      onUpdated();
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  if (curriculum.status === "draft") {
    return (
      <div className="rounded-lg border border-border bg-card p-4">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="text-sm font-semibold text-foreground">Curriculum review flow</h4>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Submit this curriculum for a lecturer to review before publishing to Moodle.
            </p>
          </div>
          <StatusBadge tone={badge.tone} label={badge.label} />
        </div>
        <div className="mt-4">
          <Button onClick={handleSubmitForReview} disabled={loading}>
            {loading ? "Submitting…" : "Submit for review"}
          </Button>
        </div>
      </div>
    );
  }

  if (curriculum.status === "awaiting_review") {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="text-sm font-semibold text-foreground">Awaiting lecturer decision</h4>
            <p className="mt-0.5 text-xs text-amber-800">
              Review the weekly plan and approve or reject.
            </p>
          </div>
          <StatusBadge tone={badge.tone} label={badge.label} />
        </div>

        <div className="mt-4 space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="reviewer-name">Reviewer name</Label>
            <Input
              id="reviewer-name"
              placeholder="e.g. Dr. Jane Lecturer"
              value={reviewerName}
              onChange={(e) => setReviewerName(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="review-comments">Comments</Label>
            <Textarea
              id="review-comments"
              placeholder="Optional feedback…"
              value={comments}
              onChange={(e) => setComments(e.target.value)}
              className="min-h-[80px]"
            />
          </div>
          <div className="flex gap-2">
            <Button
              variant="success"
              disabled={loading}
              onClick={() => handleReview("approved")}
            >
              {loading ? "Processing…" : "Approve"}
            </Button>
            <Button
              variant="destructive"
              disabled={loading}
              onClick={() => handleReview("rejected")}
            >
              Reject
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (curriculum.status === "rejected") {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4">
        <StatusBadge tone={badge.tone} label={badge.label} />
        <p className="mt-2 text-xs text-red-800">
          This curriculum was rejected. Generate a new draft to continue the review process.
        </p>
      </div>
    );
  }

  // approved / published
  return (
    <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4">
      <div className="flex items-center justify-between">
        <div>
          <h4 className="text-sm font-semibold text-foreground">Curriculum approved</h4>
          <p className="mt-0.5 text-xs text-emerald-800">
            {curriculum.status === "published"
              ? "This curriculum has been published to Moodle."
              : "Ready to publish to Moodle."}
          </p>
        </div>
        <StatusBadge tone={badge.tone} label={badge.label} />
      </div>
      <div className="mt-3">
        <Button asChild>
          <a href={`/publish/${curriculum.id}`}>
            {curriculum.status === "published" ? "Manage on Moodle" : "Publish to Moodle"}
          </a>
        </Button>
      </div>
    </div>
  );
}
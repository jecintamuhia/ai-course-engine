# Ingestion Pipeline

## Structure detection — known gaps (WHM textbook)

Status as of 2026-10-06. Deferred to the next full re-ingestion by owner decision.

- The deterministic structure detector
  (`app/services/ingestion/structure_detector.py`) required numbered-heading
  titles to start with an uppercase letter. On the WHM textbook this silently
  dropped chapter `5.3 30-Day Certification Study Plan` and sections `1.4.1`,
  `2.1.1`, `3.2.2`, `3.3.1`, `5.2.1` (titles starting with a digit or the
  lowercase brand name `cPanel`). The pattern now admits digit-initial and
  camelCase titles and still rejects prose such as `1.2 million servers…`;
  verified against the full text: 137/137 real headings matched, 0 false
  positives. Regression tests: `tests/unit/test_structure_detector.py`.
- The stored WHM structure (document `995a7c3d-0305-4011-8b49-f52072e42e9f`)
  still has 31 chapters / 100 sections instead of 32 / 105. Its chapter-5.3
  content is chunked under chapter 5.2's page span; no topic covers the
  30-Day Study Plan.
- **Do not re-run structure detection on this document yet.** Re-detection
  deletes and recreates Chapter rows; `topics.chapter_id` is
  `ON DELETE SET NULL`, so a re-detect without a subsequent topic
  re-extraction would orphan every topic's chapter link. The safe order is:
  structure re-detect (fixed detector) → chunk relink (automatic) → topic
  re-extraction, which is blocked on OpenRouter credits (HTTP 402).
- Section-level chunk attribution is page-granular: multiple sections that
  begin on the same page produce overlapping spans, and the first match
  claims the page's chunks. 35 of 100 sections therefore show 0 assigned
  chunks even though each has 2–4 chunks in its page range. Content is not
  lost; only the `section_id` provenance is coarse. Chapter 5.4 has no
  numbered subsections in the source text, so its 47 chunks have no section.

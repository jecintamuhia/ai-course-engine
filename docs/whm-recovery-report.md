# WHM recovery and readiness report

Checked 2026-10-07 against the live `course_engine` database and the current
application migration head (`3a9b8379c5a5`). Alembic's live schema check
reported no pending upgrade operations after model metadata was aligned with
the existing migration defaults and user-email constraint. This report records
existing data; it does not create or infer topic mappings.

## Recovery decision

The referenced `build_links_final.py`, `links_final.json`, and byte-exact TSV
inputs were not present in this checkout. The live curriculum relationships
already match the supplied forensic outcome: 69 of 81 allocation slots are
linked, and the 12 listed `R` slots remain unresolved. No fuzzy title matching
or new relationship writes were performed.

The curriculum has 69 unique topic links with no duplicate topic or order
positions. Per-week link counts are:

| Week | Links | Week | Links | Week | Links | Week | Links |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 5 | 5 | 5 | 9 | 5 | 13 | 5 |
| 2 | 4 | 6 | 5 | 10 | 4 | 14 | 3 |
| 3 | 5 | 7 | 5 | 11 | 5 | 15 | 2 |
| 4 | 4 | 8 | 4 | 12 | 5 | 16 | 3 |

All 68 persisted lessons have non-null topic links matching their curriculum
unit. There are zero relinkable orphan lessons and no duplicate topic links.
Every week now has lessons. Of 69 mapped topic slots, 68 have a lesson. Week
13's `Value-Added Services and Upselling` topic remains without one: its only
linked source chunk is a package-pricing table and the section heading, which
did not support a substantive lesson. The worker recorded the missing topic and
left the job failed/retryable. Existing lessons were preserved during resume.
The 68 lessons comprise 4 lecturer-approved lessons and 64 awaiting review.
The latest resume job produced 11 lessons, completed 15 units, and failed week
13 because the remaining topic generation returned no substantive lesson.

The 12 intentionally unresolved slots are `W14`, `W24`, `W44`, `W84`, `W104`,
`W142`, `W144`, `W150`, `W151`, `W154`, `W162`, and `W163`. They must remain
review-required until source-backed mappings are supplied.

## Extracted data and coverage

For document `995a7c3d-0305-4011-8b49-f52072e42e9f`, the database contains 31
chapters, 100 sections, 101 pages, 279 chunks, 215 concepts, and 140 dependency
edges. Integrity queries found zero orphan concepts, chunks, topic-source
links, or lesson-source links; zero self-dependencies, cycles, cross-document
edges, or duplicate dependency edges.

Coverage was measured by whether a section has a source chunk attached to a
topic linked into this curriculum. On that evidence, 44/100 sections are
covered and 56/100 have no mapped topic provenance. QA reports four chapters
with no topics mapped:

- MySQL Database Administration
- Cron Jobs — Scheduling Automated Tasks
- Legal and Compliance Framework for Hosting Providers
- Professional Certification Preparation

The original PDF at the supplied path was available and parsed with the
project's page-aware extractor: 101 pages and 28,993 extracted words. The
extracted text contains numbered headings through section 5.4 and a Capstone.
The 44/100 section coverage figure is still based on persisted topic-to-chunk
provenance; a heading's presence in the PDF does not count as curriculum
coverage.

## Publication state

At the initial audit, curriculum
`643a805c-050d-4910-bf2d-97da7ef68dfb` was `PUBLISHED` with a failing QA report.
It was moved back to `APPROVED` with a guarded update, and remains `APPROVED`.
Generation has since filled weeks 12-16 and all but one mapped topic. The
latest persisted QA report is version 8, verdict `fail`, with one blocking
`topic_without_lesson` finding. Missing lessons for mapped topics are blocking.
The curriculum is not eligible for republishing until the missing topic has
adequate source material and every new lesson has lecturer approval. The prior Moodle course
remains in place: its database record has course ID `5`, 16 sections, and 4
resources, with last sync 2026-09-28. The API's review and Moodle-publish routes
rerun QA and block on errors, so a republish is not ready. A live read-only
Moodle preflight passed; required custom plugin functions, capabilities, and
category were available. `core_course_get_contents` returned 17 Moodle
sections (General plus Weeks 1-16), one forum and four Page activities. All four
Pages are in Week 1; Weeks 2-16 have no activities. Moodle has not been
synchronized with the new lessons, and student login/access was not verified.

## Resume steps

1. Add textbook evidence for `Value-Added Services and Upselling` or keep the
   topic unresolved; do not generate a lesson from the price table alone.
2. Resolve the 12 `R` mappings only with source evidence and lecturer review.
3. Review the 56 uncovered sections, four uncovered chapters, progression and
   prerequisite-order findings, and the unscheduled capstone.
4. Obtain lecturer approval for generated lessons, then publish and verify the
   Moodle course and a later-week lesson with a student account.

# WHM Phase 2 progress and production blockers

Checked 2026-10-08 using the Phase 2A report built from the authenticated API
snapshot, `backend/textbook_whm.txt`, the prior recovery report, and current
application code. The WHM PDF itself is not present in this checkout. The
configured PostgreSQL hostname failed DNS resolution in both sandboxed and
approved elevated shell runs, so no live database writes or fresh database
read-backs were possible. No source provenance, lesson, curriculum, QA, Moodle,
or approval state was modified in this continuation.

## Phase 2A — coverage classification

The detailed per-section evidence, chunk excerpts, topic links, and provisional
classification are in [whm-phase2a-coverage.json](whm-phase2a-coverage.json).
The summary and classification definitions are in
[whm-phase2a-coverage.md](whm-phase2a-coverage.md).

| Classification | Sections | Interpretation |
|---|---:|---|
| COVERED | 44 | Existing scheduled curriculum topic has section-level provenance |
| C | 23 | Existing topic likely represents section, but its section/chapter provenance assignment is broken |
| E | 14 | Topic/source relationship exists, but topic is not scheduled |
| D | 8 | No defensible existing topic match; source exists, extraction/scope decision needed |
| H | 11 | Some topic links exist, but available evidence does not establish a safe match |

All 100 section titles appear in page-range source chunks. This confirms
extraction presence, not curriculum coverage. Current section-level assignments
are incomplete or attached to adjacent sections. The 20 exact heading/topic
matches listed in the dry-run
[Phase 2B plan](whm-phase2b-provenance-plan.json) are candidates for targeted
repair; three short fragments were deliberately excluded. The DB write was not
attempted again after the configured host remained unresolvable. Thus 44/100
remains the last verified persisted coverage figure; no repaired count is
claimed.

There are no sections classified as genuinely irrelevant (A) based on the
present evidence. The textbook overview includes administration, scheduling,
legal/business material, certification, and practical capstone work. Out of
scope decisions require lecturer confirmation rather than inference from
missing mappings.

## Phase 2C — four chapters

The current snapshot contradicts the older report's phrase “four chapters with
no topics”: each has topic rows, but none of those chapter's topics is scheduled.
All are part of the textbook scope; this is a curriculum allocation gap, not
proof those chapters have no extracted topics.

| Chapter | Sections | Extracted topic rows | Scheduled | Finding |
|---|---:|---:|---:|---|
| MySQL Database Administration | 3 | 3 | 0 | In scope; 1.7.1 and 1.7.2 have topic candidates; 1.7.3 exact title/topic match is a provenance repair candidate. |
| Cron Jobs — Scheduling Automated Tasks | 2 | 2 | 0 | In scope; 2.7.1 has “Cron Jobs and Scheduling”; 2.7.2 has exact “Configuring Cron Jobs” candidate. |
| Legal and Compliance Framework for Hosting Providers | 3 | 3 | 0 | In scope; 4.4.1 has several related links needing scope review; 4.4.2 and 4.4.3 have exact candidate topics. |
| Professional Certification Preparation | 2 | 2 | 0 | In scope; 5.2.2 and 5.2.3 have no defensible topic links in this snapshot and need evidence-backed extraction or lecturer decision. |

The curriculum should represent these chapters, but adding them to weeks
requires a current workload/progression review and DB access. Do not create
generic replacement topics.

## Phase 2D — capstone

The extracted text contains `Capstone Exercise 1 — Deploy a Complete Website`
and a `WordPress Mastery Capstone`; the 24-day study plan points the learner to
Section 5.1 for the latter. The snapshot also contains an existing topic named
`End-to-End Website Deployment Capstone`. A final structural record is titled
`Comprehensive Final Examination — Section 5 Capstone`, but it has zero detected
sections, five topic rows, and two scheduled topics. The prior audit says the
capstone is unscheduled, so the current data does not establish that the
existing topic is the actual final capstone or that its full source is mapped.

Decision: do not create a generic capstone lesson or schedule by assumption.
Repair chapter/section extraction and inspect source chunks and those five
topic records in the live database first. The textbook supports an integrated
practical capstone, but its exact assessment tasks and topic identity require
that read-back.

## Phase 2E — Value-Added Services and Upselling

The full extracted text has the course-level objective “Calculate hosting
pricing with appropriate margins and upsell strategies” and section 4.2.3,
`Value-Added Services and Upselling`. The section material is a priced add-on
table (SSL, backup, dedicated IP, spam filtering, managed WordPress, migration,
speed, monitoring) and a heading. A complete-text search found no explanatory
sales process, customer qualification, ethical upsell method, or worked
upselling example elsewhere. The linked source chunk is the preceding reseller
package price table plus heading. This is insufficient evidence for a
substantive strategy lesson.

Decision: leave the topic without a generated lesson, keep `topic_without_lesson`
as a blocking QA finding, and request lecturer-supplied source evidence or
approval of a narrowly table-based learning outcome. Do not regenerate the
lesson from this evidence.

## Phase 2F — unresolved recovered allocation slots

The 12 slots remain `UNRESOLVED_REVIEW`: W14, W24, W44, W84, W104, W142, W144,
W150, W151, W154, W162, W163. The original allocation-title list and recovery
inputs (`build_links_final.py`, `links_final.json`, and byte-exact TSV) are
absent from this checkout, as recorded in the prior audit. Without the original
titles, a comparison against current topics and textbook evidence cannot be
reproduced. Do not force a mapping or report a confidence level. Recover those
inputs before reclassification.

## Phase 2G–2N — status

The curriculum remains not ready on the last verified state: 69/81 allocation
slots mapped, 12 unresolved, 68 lessons for 69 mapped topics, 64 lessons
awaiting lecturer review, 44/100 textbook sections covered by scheduled topic
provenance, and latest QA fail due to `topic_without_lesson`. The four chapters
above have no scheduled topics; capstone identity/scheduling is unresolved.
The approval API code requires QA pass before curriculum approval; the 64
awaiting-review lessons were not approved. This code inspection does not prove
the production UI or current live authorization behavior.

Moodle status and student journey are only as stated in the 2026-10-07 recovery
report: stale course data; no later-week activities; student access unverified.
The PDF, Moodle endpoint, student account, and live DB were unavailable in this
continuation, so no republish or live student verification occurred. Skillup
Action Africa branding and Google OAuth requirements/configuration remain
unverified here; credentials are still an external dependency per the prior
audit.

Final status: **NOT READY**.

### Required next steps

1. Restore the configured database host/DNS, then re-read and transactionally
   apply only the section-specific provenance repairs in the Phase 2B plan;
   verify every new edge resolves to a WHM document chunk and re-run coverage.
2. Inspect the final capstone chapter's five topics and source chunks, repair
   extraction structure, and schedule only source-backed work with lecturer
   approval.
3. Obtain source evidence or lecturer disposition for Value-Added Services;
   keep QA blocked until the mapped topic has an evidence-supported lesson or
   is correctly reclassified.
4. Recover original R allocation inputs; resolve only with documented evidence.
5. Review curriculum scope, learning progression, dependencies, workload,
   and awaiting-review lessons. Run QA; do not publish until it passes and the
   required lecturer approvals are recorded.
6. Verify Moodle connection and read back current course/activities, branding,
   and a real student journey, including a Week 12+ lesson.
7. Complete the requested regression commands after data repairs and any code
   changes.

# WHM Phase 2A — Section coverage investigation

Snapshot: 2026-10-08 from the running local API and its live database. The
structured, per-section evidence is in [whm-phase2a-coverage.json](whm-phase2a-coverage.json).
That file records section/chapter IDs, persisted section chunks, chunks on the
section's page range, topic provenance, topic chapter agreement, curriculum
week, and short source excerpts. Topic-source chunk IDs were checked against
the WHM document's chunk list.

## Current evidence counts

| Finding | Count |
| --- | ---: |
| Textbook chapters / sections / pages / chunks | 31 / 100 / 101 / 279 |
| Extracted topics / curriculum-scheduled topics | 122 / 69 |
| Sections with topic provenance and a scheduled topic | 44 |
| Sections with topic provenance, but only unscheduled topic(s) | 14 |
| Sections with section-linked chunks but no topic provenance | 7 |
| Sections with neither section-linked chunks nor topic provenance | 35 |

The extracted chunk set contains an exact normalized section heading in a
page-range chunk for all 100 sections. This confirms that the source text is
present in the persisted extraction. It does **not** by itself prove a topic
mapping: 47 of the 56 uncovered sections have some topic-source link on a
heading-containing chunk, but only exact-title and concept/context checks can
establish whether that link is relevant.

The last three rows total 56 sections without mapped curriculum provenance.
For all 35 sections in the last row, the section's page range does contain
chunks. Many of those chunks are assigned to an adjacent section ID; some
contain the section heading itself. Therefore “no section chunks” is a broken
section/chunk association in at least part of this group, not evidence that the
textbook omits the material. The JSON preserves page-range candidates so each
can be checked before any relationship is rewritten.

## Discrepancy with the prior report

The earlier report named four chapters as having no topics. The current live
database has topic rows for all four, but none of their topics is scheduled:

| Chapter | Sections | Topic rows | Scheduled in current curriculum | Initial finding |
| --- | ---: | ---: | ---: | --- |
| MySQL Database Administration | 3 | 3 | 0 | Existing source topics for 1.7.1 and 1.7.2 are unscheduled; 1.7.3 has no section-linked chunk/provenance. |
| Cron Jobs — Scheduling Automated Tasks | 2 | 2 | 0 | Existing topic provenance is unscheduled; section 2.7.2 has no section-linked chunk/provenance. |
| Legal and Compliance Framework for Hosting Providers | 3 | 3 | 0 | 4.4.1 has topic provenance, while 4.4.2 and 4.4.3 lack it. |
| Professional Certification Preparation | 2 | 2 | 0 | Source chunks exist for both sections, but neither has topic provenance. |

All four are in scope indicated by the textbook itself: its course overview
explicitly includes database administration, cron automation, business/legal
content, and certification preparation. None should be classified as
irrelevant on current evidence. Their topics must not be treated as scheduled
coverage merely because topic rows exist.

## Provisional classification of the 56 uncovered sections

The structured report classifies each of the 100 section rows. The current
provisional result for the 56 uncovered rows is:

| Class | Count | Interpretation |
| --- | ---: | --- |
| C | 23 | Exact section heading plus an existing linked topic whose title matches; source/chapter association is broken. |
| D | 8 | Heading/chunk evidence exists but no topic-source candidate is linked; likely extraction gaps, requiring a source-backed topic or scope review. |
| E | 14 | Existing section-specific source-backed topic(s), but no curriculum allocation. |
| H | 11 | Topic-source links exist, but title/concept evidence does not yet establish the section mapping. |

* **E — absent from curriculum scheduling (14):** the database already has
  topic-to-source-chunk evidence for the section, but those topics have no
  curriculum allocation. The JSON's `SOURCE_PROVENANCE_TOPIC_UNSCHEDULED` rows
  identify each one.
* **C — broken section/chunk relationship (23):** an exact heading-containing
  chunk already links to a matching existing topic, but the chunk's stored
  section association does not point to that heading's section. The candidate
  chunk IDs and topic links are listed. These are Phase 2B repair candidates.
* **H — lecturer/source review (11):** source links are present on heading
  chunks, but the linked topic title is not enough to establish that it
  represents the section. The links remain unresolved until the concepts and
  full chunk context are checked.
* **D — extraction gap (8):** section headings and source chunks exist, but
  no topic-source link is present for a relevant topic. These are candidates
  for source-grounded topic extraction, not fabricated coverage. The
  WordPress troubleshooting topic is treated as a C candidate after manual
  review: its persisted topic row is misfiled under certification, while its
  concepts and page-79 source chunks support section 5.1.7. The chapter page
  span is inconsistent with that source page, so its chapter reassignment still
  requires review.

No section is marked A (out of scope) or F (legitimately merged). The D rows
have explicit textbook headings and extracted content, so they are genuine
topic-extraction gaps; whether to add the resulting topics and allocate them
is a curriculum-scope decision handled in the next phases. H rows stay
unresolved until the source context supports or rejects the candidate links.

## Source availability and next action

The original WHM PDF is not present in this workspace. The complete available
extraction is [backend/textbook_whm.txt](../backend/textbook_whm.txt), and the
database retains the page-aware extraction and chunks. Phase 2B should now
validate the 35 page-range candidates and the 7 chunks without topic links,
then repair only links for which heading, chapter/page, concept, and chunk
content agree. The 14 unscheduled source-backed topics should be evaluated
against the existing 16-week allocation before deciding whether targeted
curriculum slots are required.

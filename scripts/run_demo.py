"""End-to-end demo: PDF → curriculum → Moodle publish.

Drives the live API (default http://localhost:8000) through the entire
pipeline:

    1. generate (or reuse) the sample textbook PDF
    2. upload          POST /documents
    3. extract pages   POST /documents/{id}/extract
    4. detect structure POST /documents/{id}/detect-structure
    5. chunk           POST /documents/{id}/chunk
    6. AI topic analysis POST /documents/{id}/analyze        (slow, LLM)
    7. dependency graph POST /documents/{id}/dependencies
    8. generate curriculum POST /curricula
    9. submit for review POST /curricula/{id}/submit-for-review
    10. approve         POST /curricula/{id}/review
    11. Moodle publish  POST /moodle/publish/{id}            (--publish flag + env)
    12. verify          POST /moodle/verify/{course_id}

Set API_BASE_URL to override the API address. Publishing requires the
--publish flag AND working MOODLE_URL/MOODLE_TOKEN in backend/.env;
without --publish the demo stops after review approval with a clear
message.

Usage (run with the project virtualenv python, from the repo root):

    .venv\\Scripts\\python scripts\\run_demo.py
    .venv\\Scripts\\python scripts\\run_demo.py --publish
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
TEXTBOOK_PATH = REPO_ROOT / "storage" / "sample_ml_textbook.pdf"

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000/api/v1")

TOTAL_WEEKS = int(os.environ.get("DEMO_TOTAL_WEEKS", "16"))
LEARNING_DAYS_PER_WEEK = int(os.environ.get("DEMO_DAYS_PER_WEEK", "5"))
HOURS_PER_DAY = int(os.environ.get("DEMO_HOURS_PER_DAY", "4"))


def _banner(text: str) -> None:
    print("\n" + "=" * 72)
    print(f"  {text}")
    print("=" * 72)


def _check(client: httpx.Client, response: httpx.Response, label: str) -> None:
    if response.status_code >= 400:
        print()
        print(f"  [FAIL] Stage failed: {label}")
        print(f"  [FAIL] HTTP {response.status_code}")
        print(response.text[:2000])
        print(
            "\n  Demo stopped at this stage. The curriculum produced so "
            "far is unaffected; re-run the demo once the issue is fixed."
        )
        sys.exit(1)
    print(f"  [ok]   {label}: HTTP {response.status_code}")


def _ensure_textbook() -> Path:
    if TEXTBOOK_PATH.exists():
        return TEXTBOOK_PATH
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from generate_sample_textbook import generate

    return generate(TEXTBOOK_PATH)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="End-to-end demo of the AI Course Engine pipeline."
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help=(
            "Publish the approved curriculum to Moodle and verify it. "
            "Requires MOODLE_URL/MOODLE_TOKEN in backend/.env. Without "
            "this flag the demo stops right after lecturer approval."
        ),
    )
    args = parser.parse_args()

    _banner("AI Course Engine - End-to-End Demo")

    textbook = _ensure_textbook()
    print(f"  Using textbook: {textbook}")

    try:
        _run_pipeline(textbook, publish=args.publish)
    except httpx.HTTPError as exc:
        print()
        print(f"  [FAIL] Could not reach the API at {API_BASE_URL}.")
        print(f"  [FAIL] {type(exc).__name__}: {exc}")
        print("  Is the API running? Start it with: docker compose up -d api")
        sys.exit(1)


def _run_pipeline(textbook: Path, publish: bool) -> None:
    with httpx.Client(base_url=API_BASE_URL, timeout=1800.0) as client:
        # 1. Upload
        _banner("1. Upload document")
        with textbook.open("rb") as fh:
            response = client.post(
                "/documents",
                files={"file": (textbook.name, fh, "application/pdf")},
            )
        _check(client, response, "upload")
        document = response.json()["document"]
        document_id = document["id"]
        print(f"  document_id={document_id}")
        print(f"  filename={document['original_filename']} status={document['status']}")

        # 2. Extract pages
        _banner("2. Extract pages")
        response = client.post(f"/documents/{document_id}/extract")
        _check(client, response, "extract")
        page_count = response.json()["page_count"]
        print(f"  pages extracted: {page_count}")

        # 3. Detect structure
        _banner("3. Detect structure")
        response = client.post(f"/documents/{document_id}/detect-structure")
        _check(client, response, "detect-structure")
        chapters = response.json()["chapters"]
        print(f"  chapters detected: {len(chapters)}")
        for chapter in chapters:
            print(
                f"    - {chapter['title']} "
                f"(pages {chapter['start_page']}-{chapter['end_page']}, "
                f"{len(chapter['sections'])} sections)"
            )

        # 4. Chunk
        _banner("4. Chunk")
        response = client.post(f"/documents/{document_id}/chunk")
        _check(client, response, "chunk")
        chunk_count = response.json()["chunk_count"]
        print(f"  chunks created: {chunk_count}")

        # 5. AI topic analysis
        _banner("5. AI topic analysis (LLM - this can take a few minutes)")
        started = time.monotonic()
        response = client.post(f"/documents/{document_id}/analyze")
        _check(client, response, "analyze")
        analysis = response.json()
        print(
            f"  topics extracted: {analysis['topic_count']} "
            f"({time.monotonic() - started:.0f}s)"
        )

        # 6. Dependency graph
        _banner("6. Dependency graph")
        response = client.post(f"/documents/{document_id}/dependencies")
        _check(client, response, "dependencies")
        deps = response.json()
        print(f"  topological order: {len(deps['topological_order'])} topics")
        print(f"  unresolved prerequisites: {len(deps['unresolved_prerequisites'])}")

        # 7. Generate curriculum
        _banner("7. Generate curriculum")
        response = client.post(
            "/curricula",
            json={
                "document_id": document_id,
                "total_weeks": TOTAL_WEEKS,
                "learning_days_per_week": LEARNING_DAYS_PER_WEEK,
                "hours_per_day": HOURS_PER_DAY,
            },
        )
        _check(client, response, "generate curriculum")
        curriculum = response.json()["curriculum"]
        curriculum_id = curriculum["id"]
        print(
            f"  curriculum_id={curriculum_id} "
            f"status={curriculum['status']} "
            f"version={curriculum['version_number']}"
        )
        print(f"  planned weeks: {len(curriculum['units'])}")
        for unit in curriculum["units"]:
            topics = ", ".join(t["title"] for t in unit["topics"])
            print(
                f"    Week {unit['week_number']}: {topics} "
                f"(workload {unit['estimated_workload_minutes']}min)"
            )

        # 8. Submit for review
        _banner("8. Submit for lecturer review")
        response = client.post(f"/curricula/{curriculum_id}/submit-for-review")
        _check(client, response, "submit for review")
        print(f"  status -> {response.json()['status']}")

        # 9. Review (approve)
        _banner("9. Lecturer review: APPROVED")
        response = client.post(
            f"/curricula/{curriculum_id}/review",
            json={
                "decision": "approved",
                "reviewer_name": "Dr. Demo Lecturer",
                "comments": "Approved for the 4-month pilot cohort.",
            },
        )
        _check(client, response, "review")
        print(f"  status -> {response.json()['status']}")

        # 10. Moodle status
        _banner("10. Moodle connection status")
        response = client.get("/moodle/status")
        _check(client, response, "moodle status")
        status = response.json()
        print(
            f"  configured={status['configured']} "
            f"connected={status['connected']} site={status['site_name']}"
        )

        # 11-12. Publish + verify (only with --publish)
        configured = status.get("configured")
        if not configured:
            print(
                "\n  Moodle is not configured (MOODLE_URL/MOODLE_TOKEN "
                "missing), so the demo stops here.\n"
                "  The curriculum is APPROVED and ready to publish once "
                "Moodle credentials are set."
            )
            return

        if not publish:
            print(
                "\n  Moodle is configured, but the demo was run WITHOUT "
                "--publish, so it stops here.\n"
                "  The curriculum is APPROVED and can be published via the "
                "web UI, or by re-running:\n"
                f"    {sys.executable} {Path(sys.argv[0]).name} "
                "--publish"
            )
            return

        _banner("11. Publish to Moodle")
        response = client.post(f"/moodle/publish/{curriculum_id}", json={})
        _check(client, response, "publish")
        publish = response.json()
        print(
            f"  moodle_course_id={publish['moodle_course_id']} "
            f"created={publish['created']}"
        )
        print(
            f"  sections={publish['sections_published']} "
            f"resources={publish['resources_published']}"
        )
        print(f"  url={publish['course_url']}")

        _banner("12. Verify published course")
        response = client.post(f"/moodle/verify/{publish['course_id']}")
        _check(client, response, "verify")
        verification = response.json()
        print(
            f"  sections_found={verification['sections_found']} "
            f"modules_found={verification['modules_found']}"
        )
        for name in verification["section_names"]:
            print(f"    - {name}")


if __name__ == "__main__":
    main()
    print("\nDemo complete.")
